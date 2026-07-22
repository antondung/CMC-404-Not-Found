from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
import hashlib

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas import ContentSourceType, NliLabel


class MisconceptionStatus(StrEnum):
    OPEN = "open"
    REVIEWING = "reviewing"
    CORRECTED = "corrected"
    RESOLVED = "resolved"


class TemporalMisconceptionVerdict(StrEnum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    PARTIALLY_INCORRECT = "PARTIALLY_INCORRECT"
    OUTDATED_BUT_PREVIOUSLY_TRUE = "OUTDATED_BUT_PREVIOUSLY_TRUE"
    UNVERIFIABLE = "UNVERIFIABLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ClaimOccurrenceEvidence(BaseModel):
    """Source-neutral, provenance-complete input for misconception clustering."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    ykien_id: str = Field(min_length=1)
    content_id: str = Field(min_length=1)
    source_type: ContentSourceType
    provider: str = Field(min_length=1)
    canonical_url: str = Field(min_length=1)
    content_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    published_at: datetime
    claim_text: str = Field(min_length=3, max_length=10_000)
    evidence_span: str = Field(min_length=3, max_length=20_000)
    evidence_start: int = Field(ge=0)
    evidence_end: int = Field(gt=0)
    source_text: str = Field(min_length=3, exclude=True)
    topic: str = Field(min_length=1, max_length=200)
    legal_anchor_id: str = Field(min_length=1)
    nli_label: NliLabel
    nli_score: float = Field(ge=0, le=1)
    engagement_score: float = Field(default=0.0, ge=0, le=1)

    @model_validator(mode="after")
    def validate_provenance(self) -> "ClaimOccurrenceEvidence":
        if not self.canonical_url.lower().startswith(("http://", "https://")):
            raise ValueError("canonical_url must use http or https")
        if self.published_at.tzinfo is None or self.published_at.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
        normalized_source = " ".join(self.source_text.split())
        expected_hash = hashlib.sha256(normalized_source.encode("utf-8")).hexdigest()
        if self.content_hash != expected_hash:
            raise ValueError("content_hash must match normalized source text")
        if self.evidence_end <= self.evidence_start:
            raise ValueError("evidence_end must be greater than evidence_start")
        if self.evidence_end > len(self.source_text):
            raise ValueError("evidence offsets exceed source text")
        if self.source_text[self.evidence_start : self.evidence_end] != self.evidence_span:
            raise ValueError("evidence offsets must identify the exact source span")
        if self.claim_text not in self.evidence_span:
            raise ValueError("claim_text must be grounded in evidence_span")
        return self


class MisconceptionClusterCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    misconception_id: str
    canonical_claim: str
    normalized_claim: str
    topic: str
    legal_anchor_id: str
    number_signature: list[str] = Field(default_factory=list)
    negation_signature: list[str] = Field(default_factory=list)
    occurrence_count: int = Field(default=0, ge=0)
    status: MisconceptionStatus = MisconceptionStatus.OPEN


class MisconceptionAssignment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    misconception_id: str
    ykien_id: str
    canonical_claim: str
    normalized_claim: str
    similarity: float = Field(ge=0, le=1)
    created_cluster: bool
    occurrence_count: int = Field(ge=1)
    source_count: int = Field(ge=1)
    provider_count: int = Field(ge=1)
    status: MisconceptionStatus


class TemporalLegalCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    as_of: date
    provision_id: str = Field(min_length=1)
    lineage_id: str = Field(min_length=1)
    legal_text: str = Field(min_length=1)
    text_checksum: str = Field(min_length=64, max_length=64)
    effective_from: date
    effective_to: date | None = None
    label: NliLabel
    score: float = Field(ge=0, le=1)
    model: str = Field(min_length=1)
    needs_review: bool = False


class TemporalOccurrenceEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    evaluation_id: str = Field(min_length=1)
    misconception_id: str = Field(min_length=1)
    ykien_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    published_at: datetime
    current_as_of: date
    verdict: TemporalMisconceptionVerdict
    historical: TemporalLegalCheck | None = None
    current: TemporalLegalCheck | None = None
    reason_codes: list[str] = Field(default_factory=list)
    evaluated_at: datetime

    @model_validator(mode="after")
    def validate_temporal_verdict(self) -> "TemporalOccurrenceEvaluation":
        if self.published_at.tzinfo is None or self.published_at.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
        if self.current_as_of < self.published_at.date():
            raise ValueError("current_as_of cannot precede publication date")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reason_codes must be unique")
        if self.verdict == TemporalMisconceptionVerdict.OUTDATED_BUT_PREVIOUSLY_TRUE:
            if self.historical is None or self.current is None:
                raise ValueError("outdated verdict requires historical and current legal checks")
            if self.historical.provision_id == self.current.provision_id:
                raise ValueError("outdated verdict requires a legal version transition")
            if self.historical.lineage_id != self.current.lineage_id:
                raise ValueError("outdated verdict requires historical and current versions on one lineage")
            if self.historical.label != NliLabel.KHOP or self.historical.needs_review:
                raise ValueError("outdated verdict requires supported historical evidence")
            if self.current.label != NliLabel.MAU_THUAN or self.current.needs_review:
                raise ValueError("outdated verdict requires contradictory current evidence")
        return self


class RiskFactor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)
    weight: float = Field(ge=0, le=1)
    contribution: float = Field(ge=-1, le=1)
    explanation: str = Field(min_length=1)


class MisconceptionRiskAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    risk_score: float = Field(ge=0, le=1)
    severity: str = Field(pattern=r"^(low|medium|high|critical)$")
    factors: list[RiskFactor] = Field(min_length=8, max_length=8)
    assessed_at: datetime
    assessment_version: str = "risk-v2.0"


class MisconceptionEvaluationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    misconception_id: str = Field(min_length=1)
    current_as_of: date
    cluster_verdict: TemporalMisconceptionVerdict
    evaluations: list[TemporalOccurrenceEvaluation] = Field(min_length=1)
    risk: MisconceptionRiskAssessment
    persisted: bool


__all__ = [
    "ClaimOccurrenceEvidence",
    "MisconceptionAssignment",
    "MisconceptionClusterCandidate",
    "MisconceptionStatus",
    "MisconceptionEvaluationReport",
    "MisconceptionRiskAssessment",
    "RiskFactor",
    "TemporalLegalCheck",
    "TemporalMisconceptionVerdict",
    "TemporalOccurrenceEvaluation",
]
