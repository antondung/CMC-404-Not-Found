from __future__ import annotations

from typing import Any

from app.domain.amendment import LegalChangeType
from app.domain.amendment_commit import (
    AmendmentCommitOperation,
    AmendmentGraphCommitReport,
)
from app.domain.amendment_review import (
    AmendmentBatchStatus,
    AmendmentCandidateDecision,
    AmendmentReviewBatch,
    utc_now,
)
from app.exceptions import AmendmentCommitConflictError, ValidationError


_UNSUPPORTED_COMMIT_TYPES = {
    LegalChangeType.UNCHANGED,
    LegalChangeType.SPLIT,
    LegalChangeType.MERGED,
    LegalChangeType.UNCERTAIN,
}


class AmendmentCommitService:
    """Checksum-guarded graph commit with retry-safe PostgreSQL reconciliation."""

    def __init__(
        self,
        review_repository: Any,
        temporal_law_service: Any,
        graph_repository: Any,
    ) -> None:
        self.review_repository = review_repository
        self.temporal = temporal_law_service
        self.graph = graph_repository

    async def commit_review(
        self,
        *,
        batch_id: str,
        expected_revision: int,
        idempotency_key: str,
        actor_id: str,
        amending_source_vb_id: str | None = None,
    ) -> tuple[AmendmentGraphCommitReport, AmendmentReviewBatch, bool]:
        key = str(idempotency_key or "").strip()
        if len(key) < 8 or len(key) > 200:
            raise ValidationError("idempotency_key must contain 8 to 200 characters")
        batch = await self.review_repository.get_batch(str(batch_id).strip())
        if batch.status == AmendmentBatchStatus.COMMITTED:
            if batch.commit_idempotency_key != key or batch.commit_result is None:
                raise AmendmentCommitConflictError(
                    "amendment batch was committed with another idempotency key",
                    details={"batch_id": batch.batch_id},
                )
            return (
                AmendmentGraphCommitReport.model_validate(batch.commit_result),
                batch,
                False,
            )
        if batch.status != AmendmentBatchStatus.APPROVED:
            raise AmendmentCommitConflictError(
                "only an approved amendment review can be committed",
                details={"batch_id": batch.batch_id, "status": batch.status.value},
            )
        if batch.revision != expected_revision:
            raise AmendmentCommitConflictError(
                "amendment batch revision changed before commit",
                details={
                    "batch_id": batch.batch_id,
                    "expected_revision": expected_revision,
                    "current_revision": batch.revision,
                },
            )
        accepted = [
            item
            for item in batch.candidates
            if item.decision == AmendmentCandidateDecision.ACCEPTED
        ]
        if not accepted:
            raise AmendmentCommitConflictError(
                "approved amendment review has no accepted candidates"
            )
        unsupported = [
            item.candidate_id
            for item in accepted
            if item.change_type in _UNSUPPORTED_COMMIT_TYPES
        ]
        if unsupported:
            raise AmendmentCommitConflictError(
                "ambiguous or unchanged candidates are not eligible for automatic graph commit",
                details={"candidate_ids": unsupported},
            )
        missing_dates = [
            item.candidate_id for item in accepted if item.proposed_effective_from is None
        ]
        if missing_dates:
            raise AmendmentCommitConflictError(
                "accepted candidates require effective dates",
                details={"candidate_ids": missing_dates},
            )

        seen_old: dict[str, str] = {}
        seen_new: dict[str, str] = {}
        competing: list[dict[str, str]] = []
        for item in accepted:
            for provision_id, seen, side in (
                (item.old_provision_id, seen_old, "old"),
                (item.new_provision_id, seen_new, "new"),
            ):
                if provision_id is None:
                    continue
                previous = seen.get(provision_id)
                if previous is not None:
                    competing.append(
                        {
                            "side": side,
                            "provision_id": provision_id,
                            "first_candidate_id": previous,
                            "second_candidate_id": item.candidate_id,
                        }
                    )
                else:
                    seen[provision_id] = item.candidate_id
        if competing:
            raise AmendmentCommitConflictError(
                "accepted candidates contain an implicit split, merge or duplicate operation",
                details={"competing_candidates": competing},
            )

        physical_ids = list(
            dict.fromkeys(
                provision_id
                for item in accepted
                for provision_id in (item.old_provision_id, item.new_provision_id)
                if provision_id
            )
        )
        versions = await self.temporal.load_versions_by_ids(physical_ids, audience="admin")
        by_id = {item.provision_id: item for item in versions}
        if any(item.logical_vb_id != batch.target_logical_vb_id for item in versions):
            raise AmendmentCommitConflictError(
                "approved candidates no longer belong to the target logical document"
            )

        derived_sources = {
            by_id[item.new_provision_id].source_vb_id
            for item in accepted
            if item.new_provision_id is not None
        }
        requested_source = str(amending_source_vb_id or "").strip() or None
        if requested_source is None:
            if len(derived_sources) != 1:
                raise ValidationError(
                    "amending_source_vb_id is required when it cannot be derived uniquely",
                    details={"derived_source_vb_ids": sorted(derived_sources)},
                )
            requested_source = next(iter(derived_sources))
        if derived_sources and derived_sources != {requested_source}:
            raise AmendmentCommitConflictError(
                "amending source does not match accepted immutable new versions",
                details={
                    "requested_source_vb_id": requested_source,
                    "derived_source_vb_ids": sorted(derived_sources),
                },
            )

        operations: list[AmendmentCommitOperation] = []
        try:
            for item in accepted:
                operations.append(
                    AmendmentCommitOperation(
                        candidate_id=item.candidate_id,
                        change_type=item.change_type,
                        proposed_effective_from=item.proposed_effective_from,
                        confidence=item.confidence,
                        old_version=(
                            by_id[item.old_provision_id]
                            if item.old_provision_id is not None
                            else None
                        ),
                        new_version=(
                            by_id[item.new_provision_id]
                            if item.new_provision_id is not None
                            else None
                        ),
                    )
                )
        except ValueError as exc:
            raise AmendmentCommitConflictError(
                "approved amendment no longer satisfies graph invariants",
                details={"reason": str(exc)},
            ) from exc

        committed_at = utc_now()
        report = await self.graph.commit(
            batch_id=batch.batch_id,
            idempotency_key=key,
            amending_source_vb_id=requested_source,
            operations=operations,
            actor_id=actor_id,
            committed_at=committed_at,
        )
        reconciled_batch, reconciled = await self.review_repository.mark_committed(
            batch_id=batch.batch_id,
            expected_revision=expected_revision,
            idempotency_key=key,
            actor_id=actor_id,
            commit_result=report.model_dump(mode="json"),
            at=committed_at,
        )
        return report, reconciled_batch, reconciled


__all__ = ["AmendmentCommitService"]
