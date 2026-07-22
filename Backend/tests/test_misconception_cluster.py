from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import deps
from app.adapters.neo4j_social import Neo4jSocialRepository
from app.config import BE2Config, get_config
from app.domain.misconception import ClaimOccurrenceEvidence
from app.main import app
from app.schemas import ContentSourceType, NliLabel
from app.services.misconception_service import (
    MisconceptionService,
    claim_signatures,
    claim_similarity,
    normalize_claim_text,
)


def _evidence(
    claim: str = "Ngưỡng áp dụng là 200 triệu đồng",
    *,
    label: NliLabel = NliLabel.MAU_THUAN,
    score: float = 0.96,
) -> ClaimOccurrenceEvidence:
    source_text = f"Bài báo nêu rằng: {claim}. Người dân cần lưu ý."
    evidence_span = claim
    start = source_text.index(evidence_span)
    content_hash = hashlib.sha256(" ".join(source_text.split()).encode("utf-8")).hexdigest()
    return ClaimOccurrenceEvidence(
        ykien_id="claim-occurrence-1",
        content_id="news:article-1",
        source_type=ContentSourceType.NEWS,
        provider="news.example",
        canonical_url="https://news.example/article-1",
        content_hash=content_hash,
        published_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        claim_text=claim,
        evidence_span=evidence_span,
        evidence_start=start,
        evidence_end=start + len(evidence_span),
        source_text=source_text,
        topic="tax",
        legal_anchor_id="DOC::D5.K2",
        nli_label=label,
        nli_score=score,
    )


class _Repository:
    def __init__(self, candidates: list[dict[str, Any]] | None = None) -> None:
        self.candidates = candidates or []
        self.assignments: list[dict[str, Any]] = []

    async def find_misconception_candidates(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.candidates

    async def assign_misconception_occurrence(self, **kwargs: Any) -> dict[str, Any]:
        self.assignments.append(kwargs)
        evidence = kwargs["evidence"]
        return {
            "misconception_id": kwargs["misconception_id"],
            "ykien_id": evidence.ykien_id,
            "canonical_claim": kwargs["canonical_claim"],
            "normalized_claim": kwargs["normalized_claim"],
            "similarity": kwargs["similarity"],
            "created_cluster": False,
            "occurrence_count": 1,
            "source_count": 1,
            "provider_count": 1,
            "status": "open",
        }


def test_claim_normalization_preserves_numbers_and_negation() -> None:
    normalized = normalize_claim_text("KHÔNG áp dụng mức 200,5 triệu!")
    numbers, negations = claim_signatures(normalized)

    assert normalized == "không áp dụng mức 200,5 triệu"
    assert numbers == ["200,5"]
    assert negations == ["không"]
    assert claim_similarity(normalized, normalize_claim_text("không áp dụng mức 200,5 triệu")) == 1


def test_evidence_contract_rejects_inexact_offsets() -> None:
    data = _evidence().model_dump()
    data["source_text"] = "Nội dung khác hoàn toàn"
    data["content_hash"] = hashlib.sha256(data["source_text"].encode("utf-8")).hexdigest()

    with pytest.raises(ValueError, match="offsets"):
        ClaimOccurrenceEvidence.model_validate(data)


@pytest.mark.anyio
async def test_service_creates_cluster_then_reuses_safe_candidate() -> None:
    evidence = _evidence()
    repository = _Repository()
    service = MisconceptionService(
        repository,
        BE2Config(misconception_cluster_v2=True),
    )

    created = await service.assign_occurrence(evidence)
    assert created is not None
    assert created.created_cluster is True

    repository.candidates = [{
        "misconception_id": created.misconception_id,
        "canonical_claim": evidence.claim_text,
        "normalized_claim": normalize_claim_text(evidence.claim_text),
        "topic": evidence.topic,
        "legal_anchor_id": evidence.legal_anchor_id,
        "number_signature": ["200"],
        "negation_signature": [],
        "occurrence_count": 1,
        "status": "open",
    }]
    reused = await service.assign_occurrence(evidence.model_copy(update={"ykien_id": "claim-2"}))

    assert reused is not None
    assert reused.misconception_id == created.misconception_id
    assert reused.created_cluster is False
    assert len(repository.assignments) == 2


@pytest.mark.anyio
async def test_service_does_not_merge_claims_with_another_number() -> None:
    repository = _Repository([{
        "misconception_id": "existing-200",
        "canonical_claim": "Ngưỡng áp dụng là 200 triệu đồng",
        "normalized_claim": "ngưỡng áp dụng là 200 triệu đồng",
        "topic": "tax",
        "legal_anchor_id": "DOC::D5.K2",
        "number_signature": ["200"],
        "negation_signature": [],
        "occurrence_count": 2,
        "status": "open",
    }])
    service = MisconceptionService(repository, BE2Config(misconception_cluster_v2=True))

    result = await service.assign_occurrence(_evidence("Ngưỡng áp dụng là 500 triệu đồng"))

    assert result is not None
    assert result.created_cluster is True
    assert result.misconception_id != "existing-200"


@pytest.mark.anyio
async def test_service_is_disabled_and_ignores_non_contradictions() -> None:
    repository = _Repository()
    assert await MisconceptionService(repository, BE2Config()).assign_occurrence(_evidence()) is None
    enabled = MisconceptionService(repository, BE2Config(misconception_cluster_v2=True))
    assert await enabled.assign_occurrence(_evidence(label=NliLabel.KHOP)) is None
    assert repository.assignments == []


class _ApiRepository:
    async def list_misconceptions(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"misconception_id": "11111111-1111-1111-1111-111111111111", "status": "open"}]

    async def get_misconception(self, misconception_id: str) -> dict[str, Any] | None:
        return {"misconception_id": misconception_id, "occurrences": []}


@pytest.mark.anyio
async def test_misconception_api_is_hidden_by_default_and_available_when_enabled() -> None:
    repository = _ApiRepository()

    async def repository_override() -> Any:
        return repository

    async def disabled_config() -> BE2Config:
        return BE2Config(misconception_cluster_v2=False)

    app.dependency_overrides[deps.get_neo4j_repo] = repository_override
    app.dependency_overrides[get_config] = disabled_config
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            hidden = await client.get(
                "/admin/misconceptions",
                headers={"Authorization": "Bearer test-admin-phap-che"},
            )
    finally:
        app.dependency_overrides.clear()
    assert hidden.status_code == 404

    async def enabled_config() -> BE2Config:
        return BE2Config(misconception_cluster_v2=True)

    app.dependency_overrides[deps.get_neo4j_repo] = repository_override
    app.dependency_overrides[get_config] = enabled_config
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            listed = await client.get(
                "/admin/misconceptions?status=open&limit=10",
                headers={"Authorization": "Bearer test-admin-phap-che"},
            )
            detail = await client.get(
                "/admin/misconceptions/11111111-1111-1111-1111-111111111111",
                headers={"Authorization": "Bearer test-admin-phap-che"},
            )
    finally:
        app.dependency_overrides.clear()

    assert listed.status_code == 200
    assert listed.json()["data"]["count"] == 1
    assert detail.status_code == 200
    assert detail.json()["data"]["misconception_id"].endswith("111111111111")


class _SingleCursor:
    def __init__(self, record: dict[str, Any]) -> None:
        self.record = record

    async def single(self) -> dict[str, Any]:
        return self.record


class _ManagedSession:
    def __init__(self) -> None:
        self.query = ""
        self.params: dict[str, Any] = {}

    async def __aenter__(self) -> "_ManagedSession":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def execute_write(self, callback: Any) -> Any:
        return await callback(self)

    async def run(self, query: str, **params: Any) -> _SingleCursor:
        self.query = query
        self.params = params
        return _SingleCursor({
            "misconception_id": params["misconception_id"],
            "ykien_id": params["ykien_id"],
            "canonical_claim": params["canonical_claim"],
            "normalized_claim": params["normalized_claim"],
            "similarity": params["similarity"],
            "created_cluster": False,
            "occurrence_count": 1,
            "source_count": 1,
            "provider_count": 1,
            "status": "open",
        })


class _ManagedDriver:
    def __init__(self) -> None:
        self.session_instance = _ManagedSession()

    def session(self) -> _ManagedSession:
        return self.session_instance


@pytest.mark.anyio
async def test_repository_assignment_uses_managed_transaction_and_provenance_edge() -> None:
    driver = _ManagedDriver()
    evidence = _evidence()
    result = await Neo4jSocialRepository(driver).assign_misconception_occurrence(
        misconception_id="11111111-1111-1111-1111-111111111111",
        canonical_claim=evidence.claim_text,
        normalized_claim=normalize_claim_text(evidence.claim_text),
        number_signature=["200"],
        negation_signature=[],
        similarity=1.0,
        evidence=evidence,
    )

    assert result["misconception_id"].endswith("111111111111")
    assert "MERGE (y)-[instance:INSTANCE_OF]->(m)" in driver.session_instance.query
    assert "existing.uuid = $misconception_id" in driver.session_instance.query
    assert "MERGE (m)-[contradicts:CONTRADICTS]->(legal)" in driver.session_instance.query
    assert "count(DISTINCT coalesce(occurrence.content_hash, occurrence.content_id))" in driver.session_instance.query
    assert driver.session_instance.params["content_hash"] == evidence.content_hash
