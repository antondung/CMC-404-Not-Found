from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import deps
from app.config import BE2Config, get_config
from app.domain.amendment import LegalChangeType
from app.domain.amendment_commit import (
    AmendmentCommitOperation,
    AmendmentGraphCommitEvidence,
    AmendmentGraphCommitReport,
    AmendmentPostgresCommitState,
)
from app.domain.amendment_review import (
    AmendmentBatchStatus,
    AmendmentCandidateDecision,
    utc_now,
)
from app.exceptions import AmendmentCommitConflictError
from app.main import app
from app.adapters.neo4j_amendment_commit import Neo4jAmendmentCommitRepository
from app.services.amendment_commit_service import AmendmentCommitService
from app.services.amendment_reconciliation_service import AmendmentReconciliationService
from app.services.amendment_review_service import AmendmentReviewService
from app.workers.arq_settings import LEGAL_WORKER_FUNCTIONS, legal_cron_jobs
from tests.test_amendment_review import (
    InMemoryReviewRepository,
    StubTemporal,
    _create,
    _pair,
)


class StubGraphCommitRepository:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def commit(self, **kwargs: Any) -> AmendmentGraphCommitReport:
        self.calls.append(kwargs)
        operations = kwargs["operations"]
        return AmendmentGraphCommitReport(
            batch_id=kwargs["batch_id"],
            idempotency_key=kwargs["idempotency_key"],
            amending_source_vb_id=kwargs["amending_source_vb_id"],
            committed_candidate_ids=[item.candidate_id for item in operations],
            superseded_edges=sum(
                item.old_version is not None and item.new_version is not None
                for item in operations
            ),
            closed_intervals=sum(item.old_version is not None for item in operations),
            approved_versions=sum(item.new_version is not None for item in operations),
            idempotent_replay=False,
            committed_by=kwargs["actor_id"],
            committed_at=kwargs["committed_at"],
            graph_mutated=True,
        )


async def _approved_review() -> tuple[Any, Any, Any, Any]:
    old, new = _pair()
    temporal = StubTemporal([old, new])
    repository = InMemoryReviewRepository()
    review_service = AmendmentReviewService(repository, temporal)
    batch, _ = await _create(review_service, old, new, key="commit-review-key-001")
    submitted = await review_service.submit_review(
        batch_id=batch.batch_id,
        expected_revision=1,
        actor_id="legal-reviewer-1",
    )
    await review_service.update_candidate(
        batch_id=batch.batch_id,
        candidate_id=batch.candidates[0].candidate_id,
        expected_revision=1,
        actor_id="legal-reviewer-2",
        fields_set={"decision"},
        decision=AmendmentCandidateDecision.ACCEPTED,
    )
    approved = await review_service.decide_review(
        batch_id=batch.batch_id,
        expected_revision=submitted.revision,
        actor_id="legal-reviewer-2",
        action="approve",
        note="Approved for separately gated commit.",
    )
    return repository, temporal, approved, (old, new)


def test_commit_migration_is_additive_and_retry_safe() -> None:
    path = Path(__file__).parents[2] / "Data/schema/postgres/012_amendment_commits.sql"
    sql = path.read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS commit_idempotency_key" in sql
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_amendment_batches_commit_key" in sql
    assert "ADD COLUMN IF NOT EXISTS commit_result JSONB" in sql


def test_reconciliation_monitor_runs_only_on_the_legal_worker_when_enabled() -> None:
    names = {function.__name__ for function in LEGAL_WORKER_FUNCTIONS}
    assert "amendment_reconciliation_monitor" in names
    assert legal_cron_jobs(BE2Config()) == []

    jobs = legal_cron_jobs(
        BE2Config(
            amendment_reconciliation_monitor_enabled=True,
            amendment_reconciliation_monitor_interval_minutes=20,
        )
    )

    assert len(jobs) == 1
    assert jobs[0].name == "amendment_reconciliation_monitor"
    assert jobs[0].minute == {0, 20, 40}


@pytest.mark.anyio
async def test_commit_service_mutates_graph_then_reconciles_postgres_idempotently() -> None:
    repository, temporal, approved, _ = await _approved_review()
    graph = StubGraphCommitRepository()
    service = AmendmentCommitService(repository, temporal, graph)

    report, committed, reconciled = await service.commit_review(
        batch_id=approved.batch_id,
        expected_revision=approved.revision,
        idempotency_key="graph-commit-key-001",
        actor_id="legal-reviewer-3",
    )
    replay_report, replay_batch, replay_reconciled = await service.commit_review(
        batch_id=approved.batch_id,
        expected_revision=approved.revision,
        idempotency_key="graph-commit-key-001",
        actor_id="legal-reviewer-3",
    )

    assert report.superseded_edges == 1
    assert report.amending_source_vb_id == "SOURCE-V2"
    assert committed.status == AmendmentBatchStatus.COMMITTED
    assert committed.commit_idempotency_key == "graph-commit-key-001"
    assert committed.commit_allowed is False
    assert reconciled is True
    assert replay_report == report
    assert replay_batch.batch_id == committed.batch_id
    assert replay_reconciled is False
    assert len(graph.calls) == 1


@pytest.mark.anyio
async def test_commit_refuses_ambiguous_candidate_before_graph_write() -> None:
    old, new = _pair()
    temporal = StubTemporal([old, new])
    repository = InMemoryReviewRepository()
    review_service = AmendmentReviewService(repository, temporal)
    batch, _ = await _create(review_service, old, new, key="commit-review-key-002")
    submitted = await review_service.submit_review(
        batch_id=batch.batch_id,
        expected_revision=1,
        actor_id="legal-reviewer-1",
    )
    await review_service.update_candidate(
        batch_id=batch.batch_id,
        candidate_id=batch.candidates[0].candidate_id,
        expected_revision=1,
        actor_id="legal-reviewer-2",
        fields_set={"change_type", "decision"},
        change_type=LegalChangeType.UNCERTAIN,
        decision=AmendmentCandidateDecision.ACCEPTED,
    )
    approved = await review_service.decide_review(
        batch_id=batch.batch_id,
        expected_revision=submitted.revision,
        actor_id="legal-reviewer-2",
        action="approve",
        note=None,
    )
    graph = StubGraphCommitRepository()

    with pytest.raises(AmendmentCommitConflictError, match="not eligible"):
        await AmendmentCommitService(repository, temporal, graph).commit_review(
            batch_id=approved.batch_id,
            expected_revision=approved.revision,
            idempotency_key="graph-commit-key-002",
            actor_id="legal-reviewer-3",
        )
    assert graph.calls == []


@pytest.mark.anyio
async def test_commit_refuses_duplicate_or_implicit_split_before_graph_write() -> None:
    repository, temporal, approved, _ = await _approved_review()
    first = approved.candidates[0]
    duplicate = first.model_copy(update={"candidate_id": "duplicate-candidate"})
    repository.batches[approved.batch_id] = approved.model_copy(
        update={"candidates": [first, duplicate]}
    )
    graph = StubGraphCommitRepository()

    with pytest.raises(AmendmentCommitConflictError, match="implicit split"):
        await AmendmentCommitService(repository, temporal, graph).commit_review(
            batch_id=approved.batch_id,
            expected_revision=approved.revision,
            idempotency_key="graph-commit-key-duplicate",
            actor_id="legal-reviewer-3",
        )
    assert graph.calls == []


class _AsyncRows:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for row in self.rows:
            yield row


class _FakeTx:
    def __init__(self, rows_by_call: list[list[dict[str, Any]]]) -> None:
        self.rows_by_call = list(rows_by_call)
        self.queries: list[str] = []

    async def run(self, query: str, **params: Any) -> _AsyncRows:
        self.queries.append(query)
        return _AsyncRows(self.rows_by_call.pop(0))


class _ReadSession:
    def __init__(self, tx: _FakeTx) -> None:
        self.tx = tx

    async def __aenter__(self) -> "_ReadSession":
        return self

    async def __aexit__(self, *_: Any) -> bool:
        return False

    async def execute_read(self, callback: Any, *args: Any) -> Any:
        return await callback(self.tx, *args)


class _ReadDriver:
    def __init__(self, tx: _FakeTx) -> None:
        self.tx = tx
        self.session_kwargs: dict[str, Any] = {}

    def session(self, **kwargs: Any) -> _ReadSession:
        self.session_kwargs = kwargs
        return _ReadSession(self.tx)


class _NeoDateTime:
    def __init__(self, value: Any) -> None:
        self.value = value

    def to_native(self) -> Any:
        return self.value


@pytest.mark.anyio
async def test_graph_transaction_is_guarded_and_reports_paired_commit() -> None:
    old, new = _pair()
    operation = AmendmentCommitOperation(
        candidate_id="candidate-1",
        change_type=LegalChangeType.TIGHTENED,
        proposed_effective_from=new.effective_from,
        confidence=0.95,
        old_version=old,
        new_version=new,
    )
    tx = _FakeTx(
        [[{
            "replay": False,
            "superseded_edges": 1,
            "closed_intervals": 1,
            "approved_versions": 1,
        }]]
    )

    report = await Neo4jAmendmentCommitRepository._commit_transaction(
        tx,
        "batch-1",
        "graph-commit-key-003",
        "SOURCE-V2",
        [operation],
        "legal-reviewer-3",
        utc_now(),
    )

    assert "amendment_commit_paired" in tx.queries[0]
    assert "text_checksum" in tx.queries[0]
    assert "NOT EXISTS" in tx.queries[0]
    assert "ON CREATE SET edge" in tx.queries[0]
    assert "ON CREATE SET amended" in tx.queries[0]
    assert report.superseded_edges == 1
    assert report.idempotent_replay is False


@pytest.mark.anyio
async def test_graph_transaction_fails_closed_when_guard_matches_no_row() -> None:
    old, new = _pair()
    operation = AmendmentCommitOperation(
        candidate_id="candidate-conflict",
        change_type=LegalChangeType.TIGHTENED,
        proposed_effective_from=new.effective_from,
        confidence=0.95,
        old_version=old,
        new_version=new,
    )
    tx = _FakeTx([[]])

    with pytest.raises(AmendmentCommitConflictError, match="no longer matches"):
        await Neo4jAmendmentCommitRepository._commit_transaction(
            tx,
            "batch-conflict",
            "graph-commit-key-004",
            "SOURCE-V2",
            [operation],
            "legal-reviewer-3",
            utc_now(),
        )


@pytest.mark.anyio
async def test_graph_reconciliation_scan_is_explicitly_read_only() -> None:
    now = utc_now()
    tx = _FakeTx(
        [[{
            "batch_id": "batch-1",
            "commit_keys": ["graph-commit-key-005"],
            "committed_by": ["legal-reviewer-3"],
            "committed_at": _NeoDateTime(now),
            "edge_count": 2,
        }]]
    )
    driver = _ReadDriver(tx)

    evidence = await Neo4jAmendmentCommitRepository(driver).list_commit_evidence(
        limit=25
    )

    assert driver.session_kwargs == {"default_access_mode": "READ"}
    assert "amendment_commit_reconciliation_evidence" in tx.queries[0]
    assert evidence[0].batch_id == "batch-1"
    assert evidence[0].edge_count == 2
    assert evidence[0].committed_at == now


class _ReconciliationGraph:
    def __init__(self, evidence: list[AmendmentGraphCommitEvidence]) -> None:
        self.evidence = evidence

    async def list_commit_evidence(self, *, limit: int) -> list[AmendmentGraphCommitEvidence]:
        return self.evidence[:limit]


class _ReconciliationReview:
    def __init__(self, states: list[AmendmentPostgresCommitState]) -> None:
        self.states = states
        self.graph_batch_ids: list[str] = []

    async def inspect_commit_reconciliation(
        self,
        *,
        graph_batch_ids: list[str],
        limit: int,
    ) -> list[AmendmentPostgresCommitState]:
        self.graph_batch_ids = graph_batch_ids
        return self.states[:limit]


def _graph_evidence(batch_id: str, key: str = "graph-commit-key-monitor") -> AmendmentGraphCommitEvidence:
    return AmendmentGraphCommitEvidence(
        batch_id=batch_id,
        commit_keys=[key],
        committed_by=["legal-reviewer-3"],
        committed_at=utc_now(),
        edge_count=1,
    )


def _postgres_state(
    batch_id: str,
    *,
    status: str = "committed",
    key: str | None = "graph-commit-key-monitor",
    event: bool = True,
) -> AmendmentPostgresCommitState:
    return AmendmentPostgresCommitState(
        batch_id=batch_id,
        status=status,
        commit_idempotency_key=key,
        committed_by="legal-reviewer-3" if key else None,
        committed_at=utc_now() if key else None,
        commit_result_present=bool(key),
        reconciliation_event_present=event,
    )


@pytest.mark.anyio
async def test_reconciliation_monitor_reports_healthy_matching_stamps() -> None:
    batch_id = "batch-monitor-healthy"
    review = _ReconciliationReview([_postgres_state(batch_id)])
    report = await AmendmentReconciliationService(
        review,
        _ReconciliationGraph([_graph_evidence(batch_id)]),
    ).check()

    assert report.status == "healthy"
    assert report.issue_count == 0
    assert review.graph_batch_ids == [batch_id]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("state", "expected_code"),
    [
        (None, "postgres_batch_missing"),
        (_postgres_state("batch-monitor", status="approved", key=None), "graph_commit_unreconciled"),
        (_postgres_state("batch-monitor", key="different-commit-key"), "commit_key_mismatch"),
        (_postgres_state("batch-monitor", key=None), "postgres_metadata_incomplete"),
        (_postgres_state("batch-monitor", event=False), "reconciliation_audit_missing"),
    ],
)
async def test_reconciliation_monitor_fails_closed_on_cross_store_gaps(
    state: AmendmentPostgresCommitState | None,
    expected_code: str,
) -> None:
    graph = _ReconciliationGraph([_graph_evidence("batch-monitor")])
    review = _ReconciliationReview([state] if state else [])

    report = await AmendmentReconciliationService(review, graph).check()

    assert report.status == "degraded"
    assert report.issue_count == 1
    assert report.issues[0].code == expected_code


def _commit_config(enabled: bool) -> BE2Config:
    return BE2Config(
        legal_provision_v2_read=True,
        amendment_preview_v2=True,
        amendment_review_v2=True,
        amendment_commit_v2=enabled,
    )


@pytest.mark.anyio
async def test_reconciliation_health_api_is_read_only_and_does_not_require_commit_flag() -> None:
    batch_id = "batch-monitor-api"
    review = _ReconciliationReview([_postgres_state(batch_id)])
    graph = _ReconciliationGraph([_graph_evidence(batch_id)])

    async def repository_override() -> Any:
        return review

    async def graph_override() -> Any:
        return graph

    async def config_override() -> BE2Config:
        return _commit_config(False)

    app.dependency_overrides[deps.get_amendment_review_repository] = repository_override
    app.dependency_overrides[deps.get_amendment_commit_repository] = graph_override
    app.dependency_overrides[get_config] = config_override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/admin/legal/amendment-reconciliation/health",
                headers={"Authorization": "Bearer test-admin-phap-che"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "healthy"


@pytest.mark.anyio
async def test_commit_api_is_hidden_while_commit_flag_is_off() -> None:
    repository, temporal, approved, _ = await _approved_review()
    graph = StubGraphCommitRepository()

    async def repository_override() -> Any:
        return repository

    async def temporal_override() -> Any:
        return temporal

    async def graph_override() -> Any:
        return graph

    async def config_override() -> BE2Config:
        return _commit_config(False)

    app.dependency_overrides[deps.get_amendment_review_repository] = repository_override
    app.dependency_overrides[deps.get_temporal_law_service] = temporal_override
    app.dependency_overrides[deps.get_amendment_commit_repository] = graph_override
    app.dependency_overrides[get_config] = config_override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/admin/legal/amendment-reviews/{approved.batch_id}/commit",
                headers={"Authorization": "Bearer test-admin-phap-che"},
                json={
                    "expected_revision": approved.revision,
                    "idempotency_key": "graph-commit-key-api-off",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert graph.calls == []


@pytest.mark.anyio
async def test_enabled_commit_api_returns_reconciled_graph_report() -> None:
    repository, temporal, approved, _ = await _approved_review()
    graph = StubGraphCommitRepository()

    async def repository_override() -> Any:
        return repository

    async def temporal_override() -> Any:
        return temporal

    async def graph_override() -> Any:
        return graph

    async def config_override() -> BE2Config:
        return _commit_config(True)

    app.dependency_overrides[deps.get_amendment_review_repository] = repository_override
    app.dependency_overrides[deps.get_temporal_law_service] = temporal_override
    app.dependency_overrides[deps.get_amendment_commit_repository] = graph_override
    app.dependency_overrides[get_config] = config_override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/admin/legal/amendment-reviews/{approved.batch_id}/commit",
                headers={"Authorization": "Bearer test-admin-phap-che"},
                json={
                    "expected_revision": approved.revision,
                    "idempotency_key": "graph-commit-key-api-on",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["reconciled"] is True
    assert data["report"]["graph_mutated"] is True
    assert data["batch"]["status"] == "committed"
    assert data["batch"]["commit_allowed"] is False
