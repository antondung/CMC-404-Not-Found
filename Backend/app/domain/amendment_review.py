from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.amendment import (
    AmendmentDiffHunk,
    AmendmentReviewRoute,
    AmendmentScoreBreakdown,
    LegalChangeType,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AmendmentBatchStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMMITTED = "committed"


class AmendmentCandidateDecision(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class AmendmentReviewCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    candidate_id: str = Field(min_length=1)
    batch_id: str = Field(min_length=1)
    old_provision_id: str | None = Field(default=None, min_length=1)
    new_provision_id: str | None = Field(default=None, min_length=1)
    lineage_id: str | None = None
    reference_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    score: AmendmentScoreBreakdown | None = None
    change_type: LegalChangeType
    review_route: AmendmentReviewRoute
    proposed_effective_from: date | None = None
    decision: AmendmentCandidateDecision = AmendmentCandidateDecision.PENDING
    reason_codes: list[str] = Field(default_factory=list)
    diff_hunks: list[AmendmentDiffHunk] = Field(default_factory=list)
    reviewer_note: str | None = Field(default=None, max_length=4_000)
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    revision: int = Field(default=1, ge=1)
    commit_allowed: Literal[False] = False
    auto_approve_eligible: Literal[False] = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_candidate(self) -> "AmendmentReviewCandidate":
        if self.old_provision_id is None and self.new_provision_id is None:
            raise ValueError("candidate requires an old or new provision")
        if self.old_provision_id == self.new_provision_id:
            raise ValueError("old and new physical provisions must be different")
        if len(set(self.reference_ids)) != len(self.reference_ids):
            raise ValueError("reference_ids must be unique")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reason_codes must be unique")
        if self.old_provision_id is None and self.change_type != LegalChangeType.ADDED:
            raise ValueError("new-only candidate must be ADDED")
        if self.new_provision_id is None and self.change_type != LegalChangeType.REMOVED:
            raise ValueError("old-only candidate must be REMOVED")
        if (
            self.old_provision_id is not None
            and self.new_provision_id is not None
            and self.change_type in {LegalChangeType.ADDED, LegalChangeType.REMOVED}
        ):
            raise ValueError("paired candidate cannot be ADDED or REMOVED")
        if self.decision == AmendmentCandidateDecision.PENDING:
            if self.reviewed_by is not None or self.reviewed_at is not None:
                raise ValueError("pending candidate cannot have reviewer metadata")
        elif not self.reviewed_by or self.reviewed_at is None:
            raise ValueError("decided candidate requires reviewed_by and reviewed_at")
        return self


class AmendmentReviewBatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    batch_id: str = Field(min_length=1)
    target_logical_vb_id: str = Field(min_length=1)
    amendment_text: str = Field(min_length=5, max_length=50_000)
    status: AmendmentBatchStatus = AmendmentBatchStatus.DRAFT
    idempotency_key: str = Field(min_length=8, max_length=200)
    request_hash: str = Field(min_length=64, max_length=64)
    preview_snapshot: dict[str, Any] = Field(default_factory=dict)
    candidates: list[AmendmentReviewCandidate] = Field(default_factory=list)
    created_by: str = Field(min_length=1)
    submitted_by: str | None = None
    submitted_at: datetime | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = Field(default=None, max_length=4_000)
    commit_idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)
    committed_by: str | None = None
    committed_at: datetime | None = None
    commit_result: dict[str, Any] | None = None
    revision: int = Field(default=1, ge=1)
    commit_allowed: Literal[False] = False
    auto_approve_eligible: Literal[False] = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_batch(self) -> "AmendmentReviewBatch":
        if not self.candidates:
            raise ValueError("review batch requires at least one candidate")
        if any(item.batch_id != self.batch_id for item in self.candidates):
            raise ValueError("every candidate must belong to the batch")
        candidate_ids = [item.candidate_id for item in self.candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidate ids must be unique")
        if self.status == AmendmentBatchStatus.DRAFT:
            if self.submitted_by is not None or self.submitted_at is not None:
                raise ValueError("draft batch cannot have submission metadata")
        if self.status in {
            AmendmentBatchStatus.IN_REVIEW,
            AmendmentBatchStatus.APPROVED,
            AmendmentBatchStatus.REJECTED,
            AmendmentBatchStatus.COMMITTED,
        } and (not self.submitted_by or self.submitted_at is None):
            raise ValueError("submitted batch requires submission metadata")
        if self.status in {
            AmendmentBatchStatus.APPROVED,
            AmendmentBatchStatus.REJECTED,
            AmendmentBatchStatus.COMMITTED,
        } and (not self.reviewed_by or self.reviewed_at is None):
            raise ValueError("decided batch requires reviewer metadata")
        if self.status == AmendmentBatchStatus.COMMITTED:
            if (
                not self.commit_idempotency_key
                or not self.committed_by
                or self.committed_at is None
                or self.commit_result is None
            ):
                raise ValueError("committed batch requires commit reconciliation metadata")
        elif any(
            value is not None
            for value in (
                self.commit_idempotency_key,
                self.committed_by,
                self.committed_at,
                self.commit_result,
            )
        ):
            raise ValueError("non-committed batch cannot have commit metadata")
        return self


class AmendmentReviewBatchSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    batch_id: str
    target_logical_vb_id: str
    status: AmendmentBatchStatus
    candidate_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    revision: int = Field(ge=1)
    created_by: str
    created_at: datetime
    updated_at: datetime
    commit_allowed: Literal[False] = False


__all__ = [
    "AmendmentBatchStatus",
    "AmendmentCandidateDecision",
    "AmendmentReviewBatch",
    "AmendmentReviewBatchSummary",
    "AmendmentReviewCandidate",
    "utc_now",
]
