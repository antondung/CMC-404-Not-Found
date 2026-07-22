from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import deps
from app.adapters.neo4j_social import Neo4jSocialRepository
from app.config import BE2Config, get_config
from app.domain.misconception import TemporalMisconceptionVerdict, TemporalOccurrenceEvaluation
from app.exceptions import TemporalLawNotFoundError
from app.main import app
from app.pipelines.social.alert_signal import AlertSignalService
from app.services.temporal_misconception_service import TemporalMisconceptionService
from tests.test_amendment_review import _pair


MISCONCEPTION_ID = "22222222-2222-2222-2222-222222222222"


def _config(enabled: bool = True) -> BE2Config:
    return BE2Config(
        legal_provision_v2_read=enabled,
        temporal_law_v2=enabled,
        misconception_cluster_v2=enabled,
        misconception_temporal_v2=enabled,
        nli_confidence_threshold=0.7,
    )


class _Repository:
    def __init__(self) -> None:
        self.saved: list[dict[str, Any]] = []

    async def get_misconception_evaluation_inputs(self, misconception_id: str, *, limit: int):
        return {
            "misconception_id": misconception_id,
            "canonical_claim": "Phạt tiền 5 triệu đồng đối với hành vi vi phạm.",
            "occurrence_count": 1,
            "source_count": 1,
            "provider_count": 1,
            "first_seen_at": datetime(2026, 6, 30, tzinfo=timezone.utc),
            "last_seen_at": datetime(2026, 6, 30, tzinfo=timezone.utc),
            "occurrences": [{
                "ykien_id": "claim-old-rule-1",
                "claim_text": "Phạt tiền 5 triệu đồng đối với hành vi vi phạm.",
                "published_at": datetime(2026, 6, 30, 8, tzinfo=timezone.utc),
                "legal_anchor_id": "01/2026/ND-CP::D5.K2.Pa",
                "source_type": "news",
                "provider": "news.example",
                "engagement_score": 0.4,
                "provenance_complete": True,
            }],
        }

    async def save_misconception_evaluation(self, **kwargs: Any) -> None:
        self.saved.append(kwargs)


class _Temporal:
    def __init__(
        self,
        *,
        fail: bool = False,
        same_version: bool = False,
        different_lineage: bool = False,
    ) -> None:
        self.old, self.current = _pair()
        self.fail = fail
        self.same_version = same_version
        if different_lineage:
            self.current = self.current.model_copy(update={"lineage_id": "OTHER-LAW::D9.K9.Pz"})

    async def resolve_version(self, identifier: str, as_of: date, *, audience: str):
        if self.fail:
            raise TemporalLawNotFoundError("missing version")
        if self.same_version:
            return self.old
        return self.old if as_of < date(2026, 7, 1) else self.current


class _NLI:
    async def nli_pair(self, premise: str, hypothesis: str) -> dict[str, Any]:
        return {
            "label": "khop" if "5 triệu" in premise else "mau_thuan",
            "score": 0.96,
            "model": "stub-dual-time-nli",
            "needs_review": False,
        }


@pytest.mark.anyio
async def test_dual_time_evaluation_proves_outdated_but_previously_true() -> None:
    repository = _Repository()
    report = await TemporalMisconceptionService(
        repository,
        _Temporal(),
        _NLI(),
        _config(),
    ).evaluate_cluster(
        MISCONCEPTION_ID,
        current_as_of=date(2026, 7, 21),
        actor_id="legal-reviewer",
    )

    evaluation = report.evaluations[0]
    assert report.cluster_verdict == TemporalMisconceptionVerdict.OUTDATED_BUT_PREVIOUSLY_TRUE
    assert evaluation.historical is not None and evaluation.historical.label.value == "khop"
    assert evaluation.current is not None and evaluation.current.label.value == "mau_thuan"
    assert evaluation.historical.provision_id != evaluation.current.provision_id
    assert len(report.risk.factors) == 8
    assert report.risk.risk_score > 0
    assert repository.saved[0]["report"] == report


@pytest.mark.anyio
async def test_heuristic_nli_cannot_authorize_temporal_verdict() -> None:
    class HeuristicNLI(_NLI):
        async def nli_pair(self, premise: str, hypothesis: str) -> dict[str, Any]:
            result = await super().nli_pair(premise, hypothesis)
            result["model"] = "heuristic-nli"
            return result

    report = await TemporalMisconceptionService(
        _Repository(),
        _Temporal(),
        HeuristicNLI(),
        _config(),
    ).evaluate_cluster(
        MISCONCEPTION_ID,
        current_as_of=date(2026, 7, 21),
        actor_id="legal-reviewer",
        dry_run=True,
    )

    assert report.cluster_verdict == TemporalMisconceptionVerdict.NEEDS_REVIEW
    assert report.evaluations[0].reason_codes == ["LOW_CONFIDENCE_OR_NLI_REVIEW"]


@pytest.mark.anyio
async def test_same_legal_version_with_inconsistent_nli_needs_review() -> None:
    class InconsistentNLI:
        def __init__(self) -> None:
            self.calls = 0

        async def nli_pair(self, premise: str, hypothesis: str) -> dict[str, Any]:
            self.calls += 1
            return {
                "label": "khop" if self.calls == 1 else "mau_thuan",
                "score": 0.98,
                "model": "inconsistent-stub",
                "needs_review": False,
            }

    report = await TemporalMisconceptionService(
        _Repository(),
        _Temporal(same_version=True),
        InconsistentNLI(),
        _config(),
    ).evaluate_cluster(
        MISCONCEPTION_ID,
        current_as_of=date(2026, 7, 21),
        actor_id="legal-reviewer",
        dry_run=True,
    )

    assert report.cluster_verdict == TemporalMisconceptionVerdict.NEEDS_REVIEW
    assert report.evaluations[0].reason_codes == ["INCONSISTENT_SAME_VERSION_NLI"]
    assert report.persisted is False


@pytest.mark.anyio
async def test_different_legal_lineages_can_never_produce_outdated_verdict() -> None:
    report = await TemporalMisconceptionService(
        _Repository(),
        _Temporal(different_lineage=True),
        _NLI(),
        _config(),
    ).evaluate_cluster(
        MISCONCEPTION_ID,
        current_as_of=date(2026, 7, 21),
        actor_id="legal-reviewer",
        dry_run=True,
    )

    assert report.cluster_verdict == TemporalMisconceptionVerdict.NEEDS_REVIEW
    assert report.evaluations[0].reason_codes == ["LEGAL_LINEAGE_MISMATCH"]


@pytest.mark.anyio
async def test_outdated_domain_contract_rejects_cross_lineage_evidence() -> None:
    report = await TemporalMisconceptionService(
        _Repository(),
        _Temporal(),
        _NLI(),
        _config(),
    ).evaluate_cluster(
        MISCONCEPTION_ID,
        current_as_of=date(2026, 7, 21),
        actor_id="legal-reviewer",
        dry_run=True,
    )
    payload = report.evaluations[0].model_dump(mode="python")
    payload["current"]["lineage_id"] = "OTHER-LAW::D9.K9.Pz"

    with pytest.raises(ValueError, match="one lineage"):
        TemporalOccurrenceEvaluation.model_validate(payload)


@pytest.mark.anyio
async def test_missing_historical_or_current_basis_is_unverifiable() -> None:
    report = await TemporalMisconceptionService(
        _Repository(),
        _Temporal(fail=True),
        _NLI(),
        _config(),
    ).evaluate_cluster(
        MISCONCEPTION_ID,
        current_as_of=date(2026, 7, 21),
        actor_id="legal-reviewer",
        dry_run=True,
    )

    assert report.cluster_verdict == TemporalMisconceptionVerdict.UNVERIFIABLE
    assert report.evaluations[0].historical is None
    assert "LEGAL_VERSION_UNAVAILABLE" in report.evaluations[0].reason_codes


@pytest.mark.anyio
async def test_claim_never_supported_is_contradicted_not_previously_true() -> None:
    class AlwaysContradiction:
        async def nli_pair(self, premise: str, hypothesis: str) -> dict[str, Any]:
            return {
                "label": "mau_thuan",
                "score": 0.97,
                "model": "always-contradiction",
                "needs_review": False,
            }

    report = await TemporalMisconceptionService(
        _Repository(),
        _Temporal(),
        AlwaysContradiction(),
        _config(),
    ).evaluate_cluster(
        MISCONCEPTION_ID,
        current_as_of=date(2026, 7, 21),
        actor_id="legal-reviewer",
        dry_run=True,
    )

    assert report.cluster_verdict == TemporalMisconceptionVerdict.CONTRADICTED
    assert report.cluster_verdict != TemporalMisconceptionVerdict.OUTDATED_BUT_PREVIOUSLY_TRUE


class _ApiRepository(_Repository):
    async def get_misconception(self, misconception_id: str) -> dict[str, Any] | None:
        return {"misconception_id": misconception_id}


@pytest.mark.anyio
async def test_temporal_evaluate_api_is_hidden_then_returns_report() -> None:
    repository = _ApiRepository()
    temporal = _Temporal()
    nli = _NLI()

    async def repository_override() -> Any:
        return repository

    async def temporal_override() -> Any:
        return temporal

    async def nli_override() -> Any:
        return nli

    async def disabled_config() -> BE2Config:
        return _config(False)

    app.dependency_overrides[deps.get_neo4j_repo] = repository_override
    app.dependency_overrides[deps.get_temporal_law_service] = temporal_override
    app.dependency_overrides[deps.get_nli_service] = nli_override
    app.dependency_overrides[get_config] = disabled_config
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            hidden = await client.post(
                f"/admin/misconceptions/{MISCONCEPTION_ID}/evaluate",
                headers={"Authorization": "Bearer test-admin-phap-che"},
                json={"current_as_of": "2026-07-21", "dry_run": True},
            )
    finally:
        app.dependency_overrides.clear()
    assert hidden.status_code == 404

    async def enabled_config() -> BE2Config:
        return _config(True)

    app.dependency_overrides[deps.get_neo4j_repo] = repository_override
    app.dependency_overrides[deps.get_temporal_law_service] = temporal_override
    app.dependency_overrides[deps.get_nli_service] = nli_override
    app.dependency_overrides[get_config] = enabled_config
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            forbidden = await client.post(
                f"/admin/misconceptions/{MISCONCEPTION_ID}/evaluate",
                headers={"Authorization": "Bearer test-admin-ops"},
                json={"current_as_of": "2026-07-21", "dry_run": True},
            )
            response = await client.post(
                f"/admin/misconceptions/{MISCONCEPTION_ID}/evaluate",
                headers={"Authorization": "Bearer test-admin-phap-che"},
                json={"current_as_of": "2026-07-21", "dry_run": True},
            )
    finally:
        app.dependency_overrides.clear()

    assert forbidden.status_code == 403
    assert response.status_code == 200
    assert response.json()["data"]["cluster_verdict"] == "OUTDATED_BUT_PREVIOUSLY_TRUE"
    assert response.json()["data"]["persisted"] is False


class _Cursor:
    def __init__(self, record: dict[str, Any]) -> None:
        self.record = record

    async def single(self) -> dict[str, Any]:
        return self.record


class _Transaction:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def run(self, query: str, **params: Any) -> _Cursor:
        self.calls.append((query, params))
        if "TemporalMisconceptionEvaluation" in query:
            return _Cursor({"evaluation_id": params["evaluation_id"]})
        return _Cursor({"misconception_id": params["misconception_id"]})


class _Session:
    def __init__(self) -> None:
        self.tx = _Transaction()

    async def __aenter__(self) -> "_Session":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def execute_write(self, callback: Any) -> Any:
        return await callback(self.tx)


class _Driver:
    def __init__(self) -> None:
        self.session_instance = _Session()

    def session(self) -> _Session:
        return self.session_instance


@pytest.mark.anyio
async def test_repository_persists_dual_bases_and_risk_in_one_managed_transaction() -> None:
    source_repository = _Repository()
    report = await TemporalMisconceptionService(
        source_repository,
        _Temporal(),
        _NLI(),
        _config(),
    ).evaluate_cluster(
        MISCONCEPTION_ID,
        current_as_of=date(2026, 7, 21),
        actor_id="legal-reviewer",
        dry_run=True,
    )
    driver = _Driver()

    await Neo4jSocialRepository(driver).save_misconception_evaluation(
        report=report.model_copy(update={"persisted": True}),
        actor_id="legal-reviewer",
    )

    calls = driver.session_instance.tx.calls
    assert len(calls) == 2
    occurrence_query, occurrence_params = calls[0]
    assert "HISTORICAL_BASIS" in occurrence_query
    assert "CURRENT_BASIS" in occurrence_query
    assert "BASED_ON_OUTDATED_VERSION" in occurrence_query
    assert "historical.text_checksum = $historical_checksum" in occurrence_query
    assert "historical.lineage_id = $historical_lineage_id" in occurrence_query
    assert occurrence_params["historical_id"] != occurrence_params["current_id"]
    assert occurrence_params["historical_lineage_id"] == occurrence_params["current_lineage_id"]
    cluster_query, cluster_params = calls[1]
    assert "risk_factors_json" in cluster_query
    assert cluster_params["cluster_verdict"] == "OUTDATED_BUT_PREVIOUSLY_TRUE"


@pytest.mark.anyio
async def test_syndicated_copies_count_once_for_risk_diversity_and_velocity() -> None:
    class SyndicatedRepository(_Repository):
        async def get_misconception_evaluation_inputs(self, misconception_id: str, *, limit: int):
            base = await super().get_misconception_evaluation_inputs(misconception_id, limit=limit)
            occurrence = base["occurrences"][0]
            base["occurrence_count"] = 3
            base["source_count"] = 3
            base["provider_count"] = 3
            base["occurrences"] = [
                {**occurrence, "ykien_id": f"syndicated-{index}", "provider": f"news-{index}.example", "content_hash": "a" * 64}
                for index in range(3)
            ]
            return base

    report = await TemporalMisconceptionService(
        SyndicatedRepository(),
        _Temporal(),
        _NLI(),
        _config(),
    ).evaluate_cluster(
        MISCONCEPTION_ID,
        current_as_of=date(2026, 7, 21),
        actor_id="legal-reviewer",
        dry_run=True,
    )

    factors = {item.code: item for item in report.risk.factors}
    assert factors["SOURCE_DIVERSITY"].score == pytest.approx(1 / 3, abs=1e-6)
    assert factors["VELOCITY"].score == pytest.approx(1 / 12, abs=1e-6)


class _AlertRepository:
    def __init__(self) -> None:
        self.saved: list[dict[str, Any]] = []

    async def find_recent_alert(self, *_: Any) -> None:
        return None

    async def save_alert(self, alert: dict[str, Any]) -> str:
        self.saved.append(alert)
        return "alert-syndication-test"


def _alert_signal(*, ykien_id: str, content_hash: str) -> dict[str, Any]:
    claim = "Ngưỡng áp dụng vẫn là 200 triệu đồng."
    return {
        "bai_dang_id": f"news:{ykien_id}",
        "ykien_id": ykien_id,
        "misconception_id": MISCONCEPTION_ID,
        "claim_text": claim,
        "evidence_span": claim,
        "post_content": claim,
        "post_url": f"https://news.example/{ykien_id}",
        "chu_de": "tax",
        "khoan_id": "DOC::D5.K2.Pa",
        "label": "mau_thuan",
        "score": 0.96,
        "content_hash": content_hash,
    }


@pytest.mark.anyio
async def test_syndicated_signals_do_not_satisfy_alert_volume_threshold() -> None:
    repository = _AlertRepository()
    service = AlertSignalService(
        repository,
        BE2Config(alert_volume_threshold=2, nli_confidence_threshold=0.7),
    )

    duplicate = await service.maybe_create_alert(
        signals=[
            _alert_signal(ykien_id="copy-1", content_hash="b" * 64),
            _alert_signal(ykien_id="copy-2", content_hash="b" * 64),
        ]
    )
    independent = await service.maybe_create_alert(
        signals=[
            _alert_signal(ykien_id="source-1", content_hash="c" * 64),
            _alert_signal(ykien_id="source-2", content_hash="d" * 64),
        ]
    )

    assert duplicate is None
    assert independent is not None
    assert independent["volume"] == 2
    assert len(repository.saved) == 1
