from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.amendment import LegalChangeType
from app.domain.legal_provision import LegalProvisionVersion


_PAIRED_COMMIT_TYPES = {
    LegalChangeType.REWORDED,
    LegalChangeType.TIGHTENED,
    LegalChangeType.LOOSENED,
}


class AmendmentCommitOperation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    candidate_id: str = Field(min_length=1)
    change_type: LegalChangeType
    proposed_effective_from: date
    confidence: float = Field(ge=0, le=1)
    old_version: LegalProvisionVersion | None = None
    new_version: LegalProvisionVersion | None = None

    @model_validator(mode="after")
    def validate_operation(self) -> "AmendmentCommitOperation":
        old = self.old_version
        new = self.new_version
        if old is None and new is None:
            raise ValueError("commit operation requires an old or new provision")
        if old is None:
            if self.change_type != LegalChangeType.ADDED:
                raise ValueError("new-only commit must be ADDED")
            if new is None or new.effective_from != self.proposed_effective_from:
                raise ValueError("ADDED commit date must match the immutable new version")
            return self
        if new is None:
            if self.change_type != LegalChangeType.REMOVED:
                raise ValueError("old-only commit must be REMOVED")
            if self.proposed_effective_from <= old.effective_from:
                raise ValueError("REMOVED commit date must be later than the old version")
            return self
        if self.change_type not in _PAIRED_COMMIT_TYPES:
            raise ValueError("paired commit type is not eligible for graph mutation")
        if old.provision_id == new.provision_id:
            raise ValueError("old and new physical versions must differ")
        if old.lineage_id != new.lineage_id or old.level != new.level:
            raise ValueError("paired commit requires the same lineage and level")
        if new.effective_from != self.proposed_effective_from:
            raise ValueError("commit date must match the immutable new version")
        if new.effective_from <= old.effective_from:
            raise ValueError("new version must start after the old version")
        if old.effective_to not in {None, new.effective_from}:
            raise ValueError("old interval conflicts with the approved commit date")
        return self


class AmendmentGraphCommitReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    batch_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=8, max_length=200)
    amending_source_vb_id: str = Field(min_length=1)
    committed_candidate_ids: list[str] = Field(min_length=1)
    superseded_edges: int = Field(ge=0)
    closed_intervals: int = Field(ge=0)
    approved_versions: int = Field(ge=0)
    idempotent_replay: bool = False
    committed_by: str = Field(min_length=1)
    committed_at: datetime
    graph_mutated: bool = True


class AmendmentGraphCommitEvidence(BaseModel):
    """Read-only graph evidence used to detect incomplete cross-store reconciliation."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    batch_id: str = Field(min_length=1)
    commit_keys: list[str] = Field(min_length=1)
    committed_by: list[str] = Field(default_factory=list)
    committed_at: datetime | None = None
    edge_count: int = Field(ge=1)


class AmendmentPostgresCommitState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    batch_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    commit_idempotency_key: str | None = None
    committed_by: str | None = None
    committed_at: datetime | None = None
    commit_result_present: bool = False
    reconciliation_event_present: bool = False

    @property
    def metadata_complete(self) -> bool:
        return bool(
            self.commit_idempotency_key
            and self.committed_by
            and self.committed_at is not None
            and self.commit_result_present
        )


class AmendmentReconciliationIssue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    batch_id: str = Field(min_length=1)
    code: Literal[
        "graph_key_conflict",
        "graph_metadata_incomplete",
        "postgres_batch_missing",
        "graph_commit_unreconciled",
        "commit_key_mismatch",
        "postgres_metadata_incomplete",
        "reconciliation_audit_missing",
    ]
    graph_commit_keys: list[str] = Field(default_factory=list)
    postgres_status: str | None = None
    postgres_commit_key: str | None = None


class AmendmentReconciliationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["healthy", "degraded"]
    scanned_graph_commits: int = Field(ge=0)
    issue_count: int = Field(ge=0)
    issues: list[AmendmentReconciliationIssue] = Field(default_factory=list)
    checked_at: datetime


__all__ = [
    "AmendmentCommitOperation",
    "AmendmentGraphCommitEvidence",
    "AmendmentGraphCommitReport",
    "AmendmentPostgresCommitState",
    "AmendmentReconciliationIssue",
    "AmendmentReconciliationReport",
]
