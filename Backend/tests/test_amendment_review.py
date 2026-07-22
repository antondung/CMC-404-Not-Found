from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import deps
from app.config import BE2Config, get_config
from app.domain.amendment_review import (
    AmendmentBatchStatus,
    AmendmentCandidateDecision,
    AmendmentReviewBatch,
    AmendmentReviewBatchSummary,
    AmendmentReviewCandidate,
)
from app.domain.amendment import AmendmentReviewRoute
from app.domain.legal_provision import ProvisionLevel, build_provision_version
from app.exceptions import (
    AmendmentReviewConflictError,
    AmendmentReviewNotFoundError,
)
from app.main import app
from app.services.amendment_review_service import AmendmentReviewService


LOGICAL_ID = "01/2026/ND-CP"


def _version(
    text: str,
    *,
    effective_from: date,
    version_no: int,
    effective_to: date | None = None,
) -> Any:
    return build_provision_version(
        logical_vb_id=LOGICAL_ID,
        source_vb_id=f"SOURCE-V{version_no}",
        level=ProvisionLevel.DIEM,
        article="5",
        clause="2",
        point="a",
        text=text,
        effective_from=effective_from,
        effective_to=effective_to,
        version_no=version_no,
    )


def _pair() -> tuple[Any, Any]:
    return (
        _version(
            "Phạt tiền 5 triệu đồng đối với hành vi vi phạm.",
            effective_from=date(2025, 1, 1),
            effective_to=date(2026, 7, 1),
            version_no=1,
        ),
        _version(
            "Phạt tiền 10 triệu đồng đối với hành vi vi phạm.",
            effective_from=date(2026, 7, 1),
            version_no=2,
        ),
    )


class StubTemporal:
    def __init__(self, versions: list[Any]) -> None:
        self.by_id = {item.provision_id: item for item in versions}
        self.calls: list[tuple[list[str], str]] = []

    async def load_versions_by_ids(self, ids: list[str], *, audience: str) -> list[Any]:
        self.calls.append((list(ids), audience))
        missing = [item for item in ids if item not in self.by_id]
        if missing:
            from app.exceptions import TemporalLawNotFoundError

            raise TemporalLawNotFoundError(
                "missing provisions", details={"missing_provision_ids": missing}
            )
        return [self.by_id[item] for item in ids]


class InMemoryReviewRepository:
    def __init__(self) -> None:
        self.batches: dict[str, AmendmentReviewBatch] = {}
        self.idempotency: dict[str, str] = {}

    async def create_batch(
        self, batch: AmendmentReviewBatch
    ) -> tuple[AmendmentReviewBatch, bool]:
        existing_id = self.idempotency.get(batch.idempotency_key)
        if existing_id:
            existing = self.batches[existing_id]
            if existing.request_hash != batch.request_hash:
                raise AmendmentReviewConflictError("idempotency conflict")
            return existing, False
        self.batches[batch.batch_id] = batch
        self.idempotency[batch.idempotency_key] = batch.batch_id
        return batch, True

    async def get_batch(self, batch_id: str) -> AmendmentReviewBatch:
        if batch_id not in self.batches:
            raise AmendmentReviewNotFoundError("batch not found")
        return self.batches[batch_id]

    async def list_batches(
        self,
        *,
        status: AmendmentBatchStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AmendmentReviewBatchSummary], int]:
        batches = list(self.batches.values())
        if status is not None:
            batches = [item for item in batches if item.status == status]
        items = [
            AmendmentReviewBatchSummary(
                batch_id=item.batch_id,
                target_logical_vb_id=item.target_logical_vb_id,
                status=item.status,
                candidate_count=len(item.candidates),
                pending_count=sum(
                    candidate.decision == AmendmentCandidateDecision.PENDING
                    for candidate in item.candidates
                ),
                revision=item.revision,
                created_by=item.created_by,
                created_at=item.created_at,
                updated_at=item.updated_at,
                commit_allowed=False,
            )
            for item in batches[offset : offset + limit]
        ]
        return items, len(batches)

    async def update_candidate(
        self,
        candidate: AmendmentReviewCandidate,
        *,
        expected_revision: int,
        actor_id: str,
    ) -> AmendmentReviewCandidate:
        batch = await self.get_batch(candidate.batch_id)
        current = next(
            item for item in batch.candidates if item.candidate_id == candidate.candidate_id
        )
        if current.revision != expected_revision:
            raise AmendmentReviewConflictError(
                "candidate revision conflict",
                details={"current_revision": current.revision},
            )
        updated = AmendmentReviewCandidate.model_validate(
            candidate.model_copy(update={"revision": current.revision + 1}).model_dump()
        )
        candidates = [
            updated if item.candidate_id == updated.candidate_id else item
            for item in batch.candidates
        ]
        self.batches[batch.batch_id] = AmendmentReviewBatch.model_validate(
            batch.model_copy(update={"candidates": candidates}).model_dump()
        )
        return updated

    async def transition_batch(
        self,
        *,
        batch_id: str,
        expected_revision: int,
        from_status: AmendmentBatchStatus,
        to_status: AmendmentBatchStatus,
        actor_id: str,
        note: str | None,
        at: Any,
    ) -> AmendmentReviewBatch:
        batch = await self.get_batch(batch_id)
        if batch.revision != expected_revision or batch.status != from_status:
            raise AmendmentReviewConflictError(
                "batch state conflict",
                details={"current_revision": batch.revision, "status": batch.status.value},
            )
        changes: dict[str, Any] = {
            "status": to_status,
            "revision": batch.revision + 1,
            "updated_at": at,
        }
        if to_status == AmendmentBatchStatus.IN_REVIEW:
            changes.update({"submitted_by": actor_id, "submitted_at": at})
        if to_status in {AmendmentBatchStatus.APPROVED, AmendmentBatchStatus.REJECTED}:
            changes.update(
                {"reviewed_by": actor_id, "reviewed_at": at, "review_note": note}
            )
        updated = AmendmentReviewBatch.model_validate(
            batch.model_copy(update=changes).model_dump()
        )
        self.batches[batch_id] = updated
        return updated

    async def mark_committed(
        self,
        *,
        batch_id: str,
        expected_revision: int,
        idempotency_key: str,
        actor_id: str,
        commit_result: dict[str, Any],
        at: Any,
    ) -> tuple[AmendmentReviewBatch, bool]:
        batch = await self.get_batch(batch_id)
        if batch.status == AmendmentBatchStatus.COMMITTED:
            if batch.commit_idempotency_key != idempotency_key:
                raise AmendmentReviewConflictError("commit key conflict")
            return batch, False
        if batch.status != AmendmentBatchStatus.APPROVED or batch.revision != expected_revision:
            raise AmendmentReviewConflictError("commit state conflict")
        updated = AmendmentReviewBatch.model_validate(
            batch.model_copy(
                update={
                    "status": AmendmentBatchStatus.COMMITTED,
                    "revision": batch.revision + 1,
                    "commit_idempotency_key": idempotency_key,
                    "committed_by": actor_id,
                    "committed_at": at,
                    "commit_result": commit_result,
                    "updated_at": at,
                }
            ).model_dump()
        )
        self.batches[batch_id] = updated
        return updated, True


async def _create(
    service: AmendmentReviewService,
    old: Any,
    new: Any,
    *,
    key: str = "amendment-review-key-001",
) -> tuple[AmendmentReviewBatch, bool]:
    return await service.create_review(
        amendment_text="Sửa đổi điểm a khoản 2 Điều 5 như sau:",
        old_provision_ids=[old.provision_id],
        new_provision_ids=[new.provision_id],
        target_logical_vb_id=LOGICAL_ID,
        idempotency_key=key,
        actor_id="legal-reviewer-1",
    )


def test_postgres_migration_keeps_review_non_committing() -> None:
    path = Path(__file__).parents[2] / "Data/schema/postgres/011_amendment_reviews.sql"
    sql = path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS amendment_review_batches" in sql
    assert "CREATE TABLE IF NOT EXISTS amendment_review_candidates" in sql
    assert "CREATE TABLE IF NOT EXISTS amendment_review_events" in sql
    assert "CHECK (commit_allowed = FALSE)" in sql
    assert "CHECK (auto_approve_eligible = FALSE)" in sql
    assert "ON DELETE RESTRICT" in sql


@pytest.mark.anyio
async def test_create_review_is_canonical_idempotent_and_non_committing() -> None:
    old, new = _pair()
    temporal = StubTemporal([old, new])
    repository = InMemoryReviewRepository()
    service = AmendmentReviewService(repository, temporal)

    batch, created = await _create(service, old, new)
    replay, replay_created = await _create(service, old, new)

    assert created is True
    assert replay_created is False
    assert replay.batch_id == batch.batch_id
    assert batch.status == AmendmentBatchStatus.DRAFT
    assert batch.commit_allowed is False
    assert batch.auto_approve_eligible is False
    assert batch.candidates[0].proposed_effective_from == date(2026, 7, 1)
    assert batch.candidates[0].decision == AmendmentCandidateDecision.PENDING
    assert all(audience == "admin" for _, audience in temporal.calls)


@pytest.mark.anyio
async def test_candidate_decision_is_rejected_before_submission() -> None:
    old, new = _pair()
    repository = InMemoryReviewRepository()
    service = AmendmentReviewService(repository, StubTemporal([old, new]))
    batch, _ = await _create(service, old, new)

    with pytest.raises(AmendmentReviewConflictError, match="only allowed after"):
        await service.update_candidate(
            batch_id=batch.batch_id,
            candidate_id=batch.candidates[0].candidate_id,
            expected_revision=1,
            actor_id="legal-reviewer-1",
            fields_set={"decision"},
            decision=AmendmentCandidateDecision.ACCEPTED,
        )


@pytest.mark.anyio
async def test_reviewer_pair_change_resets_stale_score_and_recomputes_diff() -> None:
    old, new = _pair()
    replacement = _version(
        "Phạt tiền 20 triệu đồng đối với hành vi vi phạm.",
        effective_from=date(2027, 1, 1),
        version_no=3,
    )
    repository = InMemoryReviewRepository()
    service = AmendmentReviewService(repository, StubTemporal([old, new, replacement]))
    batch, _ = await _create(service, old, new)

    updated = await service.update_candidate(
        batch_id=batch.batch_id,
        candidate_id=batch.candidates[0].candidate_id,
        expected_revision=1,
        actor_id="legal-reviewer-1",
        fields_set={"new_provision_id"},
        new_provision_id=replacement.provision_id,
    )

    assert updated.new_provision_id == replacement.provision_id
    assert updated.proposed_effective_from == date(2027, 1, 1)
    assert updated.score is None
    assert updated.confidence == 0
    assert updated.reference_ids == []
    assert updated.diff_hunks
    assert updated.review_route == AmendmentReviewRoute.MANDATORY_REVIEW
    assert "reviewer_changed_candidate_pair" in updated.reason_codes


@pytest.mark.anyio
async def test_review_workflow_uses_revision_guards_and_never_commits() -> None:
    old, new = _pair()
    repository = InMemoryReviewRepository()
    service = AmendmentReviewService(repository, StubTemporal([old, new]))
    batch, _ = await _create(service, old, new)
    submitted = await service.submit_review(
        batch_id=batch.batch_id,
        expected_revision=1,
        actor_id="legal-reviewer-1",
    )
    candidate = await service.update_candidate(
        batch_id=batch.batch_id,
        candidate_id=batch.candidates[0].candidate_id,
        expected_revision=1,
        actor_id="legal-reviewer-2",
        fields_set={"decision", "reviewer_note"},
        decision=AmendmentCandidateDecision.ACCEPTED,
        reviewer_note="Đã đối chiếu văn bản gốc.",
    )
    approved = await service.decide_review(
        batch_id=batch.batch_id,
        expected_revision=submitted.revision,
        actor_id="legal-reviewer-2",
        action="approve",
        note="Đủ điều kiện cho bước commit riêng biệt.",
    )

    assert candidate.revision == 2
    assert candidate.reviewed_by == "legal-reviewer-2"
    assert approved.status == AmendmentBatchStatus.APPROVED
    assert approved.commit_allowed is False
    assert approved.auto_approve_eligible is False

    with pytest.raises(AmendmentReviewConflictError, match="only draft"):
        await service.submit_review(
            batch_id=batch.batch_id,
            expected_revision=1,
            actor_id="legal-reviewer-1",
        )


@pytest.mark.anyio
async def test_approval_fails_while_candidate_is_pending() -> None:
    old, new = _pair()
    repository = InMemoryReviewRepository()
    service = AmendmentReviewService(repository, StubTemporal([old, new]))
    batch, _ = await _create(service, old, new)
    submitted = await service.submit_review(
        batch_id=batch.batch_id,
        expected_revision=1,
        actor_id="legal-reviewer-1",
    )

    with pytest.raises(AmendmentReviewConflictError, match="must be decided"):
        await service.decide_review(
            batch_id=batch.batch_id,
            expected_revision=submitted.revision,
            actor_id="legal-reviewer-2",
            action="approve",
            note=None,
        )


def _enabled_config() -> BE2Config:
    return BE2Config(
        legal_provision_v2_read=True,
        amendment_preview_v2=True,
        amendment_review_v2=True,
        amendment_commit_v2=False,
    )


@pytest.mark.anyio
async def test_review_api_is_hidden_while_review_flag_is_off() -> None:
    old, new = _pair()
    temporal = StubTemporal([old, new])
    repository = InMemoryReviewRepository()

    async def temporal_override() -> StubTemporal:
        return temporal

    async def repository_override() -> InMemoryReviewRepository:
        return repository

    async def config_override() -> BE2Config:
        return BE2Config(
            legal_provision_v2_read=True,
            amendment_preview_v2=True,
            amendment_review_v2=False,
        )

    app.dependency_overrides[deps.get_temporal_law_service] = temporal_override
    app.dependency_overrides[deps.get_amendment_review_repository] = repository_override
    app.dependency_overrides[get_config] = config_override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/admin/legal/amendment-reviews",
                headers={"Authorization": "Bearer test-admin-phap-che"},
                json={
                    "amendment_text": "Sửa đổi điểm a khoản 2 Điều 5 như sau:",
                    "old_provision_ids": [old.provision_id],
                    "new_provision_ids": [new.provision_id],
                    "idempotency_key": "api-review-key-001",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert repository.batches == {}


@pytest.mark.anyio
async def test_review_api_requires_legal_role_and_persists_draft() -> None:
    old, new = _pair()
    temporal = StubTemporal([old, new])
    repository = InMemoryReviewRepository()

    async def temporal_override() -> StubTemporal:
        return temporal

    async def repository_override() -> InMemoryReviewRepository:
        return repository

    async def config_override() -> BE2Config:
        return _enabled_config()

    app.dependency_overrides[deps.get_temporal_law_service] = temporal_override
    app.dependency_overrides[deps.get_amendment_review_repository] = repository_override
    app.dependency_overrides[get_config] = config_override
    payload = {
        "amendment_text": "Sửa đổi điểm a khoản 2 Điều 5 như sau:",
        "old_provision_ids": [old.provision_id],
        "new_provision_ids": [new.provision_id],
        "idempotency_key": "api-review-key-002",
    }
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            forbidden = await client.post(
                "/admin/legal/amendment-reviews",
                headers={"Authorization": "Bearer test-admin-ops"},
                json=payload,
            )
            created = await client.post(
                "/admin/legal/amendment-reviews",
                headers={"Authorization": "Bearer test-admin-phap-che"},
                json=payload,
            )
            listed = await client.get(
                "/admin/legal/amendment-reviews",
                headers={"Authorization": "Bearer test-admin-phap-che"},
            )
    finally:
        app.dependency_overrides.clear()

    assert forbidden.status_code == 403
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["created"] is True
    assert data["batch"]["commit_allowed"] is False
    assert data["batch"]["status"] == "draft"
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1


@pytest.mark.anyio
async def test_review_api_idempotent_replay_returns_200() -> None:
    old, new = _pair()
    temporal = StubTemporal([old, new])
    repository = InMemoryReviewRepository()

    async def temporal_override() -> StubTemporal:
        return temporal

    async def repository_override() -> InMemoryReviewRepository:
        return repository

    async def config_override() -> BE2Config:
        return _enabled_config()

    app.dependency_overrides[deps.get_temporal_law_service] = temporal_override
    app.dependency_overrides[deps.get_amendment_review_repository] = repository_override
    app.dependency_overrides[get_config] = config_override
    payload = {
        "amendment_text": "Sửa đổi điểm a khoản 2 Điều 5 như sau:",
        "old_provision_ids": [old.provision_id],
        "new_provision_ids": [new.provision_id],
        "idempotency_key": "api-review-key-003",
    }
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            first = await client.post(
                "/admin/legal/amendment-reviews",
                headers={"Authorization": "Bearer test-admin-phap-che"},
                json=payload,
            )
            replay = await client.post(
                "/admin/legal/amendment-reviews",
                headers={"Authorization": "Bearer test-admin-phap-che"},
                json=payload,
            )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["data"]["created"] is False
    assert (
        first.json()["data"]["batch"]["batch_id"]
        == replay.json()["data"]["batch"]["batch_id"]
    )
