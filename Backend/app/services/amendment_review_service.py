from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any
from uuid import uuid4

from app.domain.amendment import AmendmentDiffHunk, AmendmentReviewRoute, LegalChangeType
from app.domain.amendment_review import (
    AmendmentBatchStatus,
    AmendmentCandidateDecision,
    AmendmentReviewBatch,
    AmendmentReviewBatchSummary,
    AmendmentReviewCandidate,
    utc_now,
)
from app.exceptions import AmendmentReviewConflictError, ValidationError
from app.pipelines.legal.change_classifier import LegalChangeClassifier
from app.pipelines.legal.version_diff import VersionDiff
from app.services.amendment_preview_service import AmendmentPreviewService


_AMBIGUOUS_TYPES = {
    LegalChangeType.SPLIT,
    LegalChangeType.MERGED,
    LegalChangeType.UNCERTAIN,
}


class AmendmentReviewService:
    """Review-only workflow. This service has no Neo4j write dependency."""

    def __init__(
        self,
        repository: Any,
        temporal_law_service: Any,
        *,
        preview_service: AmendmentPreviewService | None = None,
    ) -> None:
        self.repository = repository
        self.temporal = temporal_law_service
        self.preview_service = preview_service or AmendmentPreviewService(temporal_law_service)
        self.classifier = LegalChangeClassifier()
        self.diff_engine = VersionDiff()

    @staticmethod
    def _clean_ids(values: list[str]) -> list[str]:
        return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))

    @staticmethod
    def _request_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    async def create_review(
        self,
        *,
        amendment_text: str,
        old_provision_ids: list[str],
        new_provision_ids: list[str],
        target_logical_vb_id: str | None,
        idempotency_key: str,
        actor_id: str,
    ) -> tuple[AmendmentReviewBatch, bool]:
        key = str(idempotency_key or "").strip()
        if len(key) < 8 or len(key) > 200:
            raise ValidationError("idempotency_key must contain 8 to 200 characters")
        old_ids = self._clean_ids(old_provision_ids)
        new_ids = self._clean_ids(new_provision_ids)
        preview = await self.preview_service.preview(
            amendment_text=amendment_text,
            old_provision_ids=old_ids,
            new_provision_ids=new_ids,
            target_logical_vb_id=target_logical_vb_id,
        )
        new_versions = await self.temporal.load_versions_by_ids(new_ids, audience="admin")
        new_by_id = {item.provision_id: item for item in new_versions}
        request_hash = self._request_hash(
            {
                "amendment_text": amendment_text.strip(),
                "old_provision_ids": old_ids,
                "new_provision_ids": new_ids,
                "target_logical_vb_id": preview.target_logical_vb_id,
            }
        )
        batch_id = str(uuid4())
        now = utc_now()
        candidates: list[AmendmentReviewCandidate] = []
        for match in preview.matches:
            new_version = new_by_id[match.new_provision_id]
            candidates.append(
                AmendmentReviewCandidate(
                    candidate_id=str(uuid4()),
                    batch_id=batch_id,
                    old_provision_id=match.old_provision_id,
                    new_provision_id=match.new_provision_id,
                    lineage_id=match.lineage_id,
                    reference_ids=match.reference_ids,
                    confidence=match.confidence,
                    score=match.score,
                    change_type=match.change_type,
                    review_route=match.review_route,
                    proposed_effective_from=new_version.effective_from,
                    reason_codes=match.reason_codes,
                    diff_hunks=match.diff_hunks,
                    created_at=now,
                    updated_at=now,
                )
            )
        for unmatched in preview.unmatched_changes:
            new_version = new_by_id.get(unmatched.provision_id)
            candidates.append(
                AmendmentReviewCandidate(
                    candidate_id=str(uuid4()),
                    batch_id=batch_id,
                    old_provision_id=(
                        unmatched.provision_id if unmatched.side == "old" else None
                    ),
                    new_provision_id=(
                        unmatched.provision_id if unmatched.side == "new" else None
                    ),
                    confidence=0,
                    score=None,
                    change_type=unmatched.change_type,
                    review_route=AmendmentReviewRoute.MANDATORY_REVIEW,
                    proposed_effective_from=(
                        new_version.effective_from if new_version is not None else None
                    ),
                    reason_codes=[unmatched.reason_code],
                    created_at=now,
                    updated_at=now,
                )
            )
        if not candidates:
            raise ValidationError("amendment preview produced no review candidates")
        batch = AmendmentReviewBatch(
            batch_id=batch_id,
            target_logical_vb_id=preview.target_logical_vb_id,
            amendment_text=amendment_text.strip(),
            idempotency_key=key,
            request_hash=request_hash,
            preview_snapshot=preview.model_dump(mode="json"),
            candidates=candidates,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        return await self.repository.create_batch(batch)

    async def get_review(self, batch_id: str) -> AmendmentReviewBatch:
        return await self.repository.get_batch(str(batch_id).strip())

    async def list_reviews(
        self,
        *,
        status: AmendmentBatchStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AmendmentReviewBatchSummary], int]:
        if limit < 1 or limit > 100:
            raise ValidationError("limit must be between 1 and 100")
        if offset < 0:
            raise ValidationError("offset must not be negative")
        return await self.repository.list_batches(status=status, limit=limit, offset=offset)

    async def update_candidate(
        self,
        *,
        batch_id: str,
        candidate_id: str,
        expected_revision: int,
        actor_id: str,
        fields_set: set[str],
        old_provision_id: str | None = None,
        new_provision_id: str | None = None,
        change_type: LegalChangeType | None = None,
        proposed_effective_from: date | None = None,
        decision: AmendmentCandidateDecision | None = None,
        reviewer_note: str | None = None,
    ) -> AmendmentReviewCandidate:
        batch = await self.repository.get_batch(batch_id)
        if batch.status not in {AmendmentBatchStatus.DRAFT, AmendmentBatchStatus.IN_REVIEW}:
            raise AmendmentReviewConflictError(
                "decided amendment review batch is immutable",
                details={"batch_id": batch_id, "status": batch.status.value},
            )
        current = next(
            (item for item in batch.candidates if item.candidate_id == candidate_id),
            None,
        )
        if current is None:
            from app.exceptions import AmendmentReviewNotFoundError

            raise AmendmentReviewNotFoundError(
                "amendment review candidate not found",
                details={"batch_id": batch_id, "candidate_id": candidate_id},
            )
        if expected_revision < 1:
            raise ValidationError("expected_revision must be positive")
        if batch.status == AmendmentBatchStatus.DRAFT and "decision" in fields_set:
            if decision not in {None, AmendmentCandidateDecision.PENDING}:
                raise AmendmentReviewConflictError(
                    "candidate decisions are only allowed after batch submission"
                )

        old_id = old_provision_id if "old_provision_id" in fields_set else current.old_provision_id
        new_id = new_provision_id if "new_provision_id" in fields_set else current.new_provision_id
        old_id = str(old_id).strip() if old_id else None
        new_id = str(new_id).strip() if new_id else None
        if old_id is None and new_id is None:
            raise ValidationError("candidate requires an old or new provision")
        if old_id == new_id:
            raise ValidationError("old and new physical versions must be different")

        ids = [item for item in [old_id, new_id] if item]
        versions = await self.temporal.load_versions_by_ids(ids, audience="admin")
        by_id = {item.provision_id: item for item in versions}
        if any(item.logical_vb_id != batch.target_logical_vb_id for item in versions):
            raise ValidationError(
                "candidate provisions must belong to the review target document",
                details={"target_logical_vb_id": batch.target_logical_vb_id},
            )

        identity_changed = old_id != current.old_provision_id or new_id != current.new_provision_id
        classified_reasons: list[str] = []
        classified_type: LegalChangeType | None = None
        if identity_changed and old_id and new_id:
            classified_type, classified_reasons = self.classifier.classify(
                by_id[old_id].text,
                by_id[new_id].text,
            )
        resolved_type = (
            change_type
            if "change_type" in fields_set
            else classified_type or current.change_type
        )
        if resolved_type is None:
            raise ValidationError("change_type is required")
        if old_id is None:
            resolved_type = LegalChangeType.ADDED
        elif new_id is None:
            resolved_type = LegalChangeType.REMOVED
        elif resolved_type in {LegalChangeType.ADDED, LegalChangeType.REMOVED}:
            raise ValidationError("paired candidate cannot be ADDED or REMOVED")

        effective = (
            proposed_effective_from
            if "proposed_effective_from" in fields_set
            else current.proposed_effective_from
        )
        if "new_provision_id" in fields_set and new_id and "proposed_effective_from" not in fields_set:
            effective = by_id[new_id].effective_from
        if effective is not None and old_id and effective <= by_id[old_id].effective_from:
            raise ValidationError("proposed_effective_from must be later than the old version")

        resolved_decision = decision if "decision" in fields_set else current.decision
        if resolved_decision is None:
            resolved_decision = current.decision
        if resolved_decision == AmendmentCandidateDecision.ACCEPTED and effective is None:
            raise ValidationError("accepted candidate requires proposed_effective_from")

        reason_codes = list(current.reason_codes)
        if identity_changed:
            reason_codes.append("reviewer_changed_candidate_pair")
            reason_codes.extend(classified_reasons)
        if (
            effective is not None
            and new_id is not None
            and effective != by_id[new_id].effective_from
        ):
            reason_codes.append("reviewer_effective_date_override")
        route = (
            AmendmentReviewRoute.MANDATORY_REVIEW
            if identity_changed
            or resolved_type in _AMBIGUOUS_TYPES
            or current.review_route == AmendmentReviewRoute.MANDATORY_REVIEW
            else AmendmentReviewRoute.HUMAN_REVIEW
        )
        reviewed_by = None
        reviewed_at = None
        if resolved_decision != AmendmentCandidateDecision.PENDING:
            reviewed_by = actor_id
            reviewed_at = utc_now()
        old_version = by_id.get(old_id) if old_id else None
        new_version = by_id.get(new_id) if new_id else None
        lineage_id = (
            old_version.lineage_id
            if old_version is not None
            and new_version is not None
            and old_version.lineage_id == new_version.lineage_id
            else None
        )
        diff_hunks = current.diff_hunks
        if identity_changed:
            diff_hunks = (
                [
                    AmendmentDiffHunk.model_validate(item)
                    for item in self.diff_engine.diff(old_version.text, new_version.text)
                ]
                if old_version is not None and new_version is not None
                else []
            )
        updated = current.model_copy(
            update={
                "old_provision_id": old_id,
                "new_provision_id": new_id,
                "lineage_id": lineage_id,
                "reference_ids": [] if identity_changed else current.reference_ids,
                "confidence": 0 if identity_changed else current.confidence,
                "score": None if identity_changed else current.score,
                "change_type": resolved_type,
                "review_route": route,
                "proposed_effective_from": effective,
                "decision": resolved_decision,
                "reason_codes": list(dict.fromkeys(reason_codes)),
                "diff_hunks": diff_hunks,
                "reviewer_note": (
                    reviewer_note if "reviewer_note" in fields_set else current.reviewer_note
                ),
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
                "updated_at": utc_now(),
            }
        )
        updated = AmendmentReviewCandidate.model_validate(updated.model_dump())
        return await self.repository.update_candidate(
            updated,
            expected_revision=expected_revision,
            actor_id=actor_id,
        )

    async def submit_review(
        self,
        *,
        batch_id: str,
        expected_revision: int,
        actor_id: str,
    ) -> AmendmentReviewBatch:
        batch = await self.repository.get_batch(batch_id)
        if batch.status != AmendmentBatchStatus.DRAFT:
            raise AmendmentReviewConflictError(
                "only draft amendment reviews can be submitted",
                details={"status": batch.status.value},
            )
        return await self.repository.transition_batch(
            batch_id=batch_id,
            expected_revision=expected_revision,
            from_status=AmendmentBatchStatus.DRAFT,
            to_status=AmendmentBatchStatus.IN_REVIEW,
            actor_id=actor_id,
            note=None,
            at=utc_now(),
        )

    async def decide_review(
        self,
        *,
        batch_id: str,
        expected_revision: int,
        actor_id: str,
        action: str,
        note: str | None,
    ) -> AmendmentReviewBatch:
        batch = await self.repository.get_batch(batch_id)
        if batch.status != AmendmentBatchStatus.IN_REVIEW:
            raise AmendmentReviewConflictError(
                "only submitted amendment reviews can be decided",
                details={"status": batch.status.value},
            )
        normalized = str(action or "").strip().lower()
        if normalized not in {"approve", "reject"}:
            raise ValidationError("action must be approve or reject")
        if normalized == "approve":
            pending = [
                item.candidate_id
                for item in batch.candidates
                if item.decision == AmendmentCandidateDecision.PENDING
            ]
            accepted = [
                item for item in batch.candidates
                if item.decision == AmendmentCandidateDecision.ACCEPTED
            ]
            if pending:
                raise AmendmentReviewConflictError(
                    "all amendment candidates must be decided before approval",
                    details={"pending_candidate_ids": pending},
                )
            if not accepted:
                raise AmendmentReviewConflictError(
                    "approved amendment review requires at least one accepted candidate"
                )
            missing_dates = [
                item.candidate_id
                for item in accepted
                if item.proposed_effective_from is None
            ]
            if missing_dates:
                raise AmendmentReviewConflictError(
                    "accepted candidates require proposed effective dates",
                    details={"candidate_ids": missing_dates},
                )
        target = (
            AmendmentBatchStatus.APPROVED
            if normalized == "approve"
            else AmendmentBatchStatus.REJECTED
        )
        return await self.repository.transition_batch(
            batch_id=batch_id,
            expected_revision=expected_revision,
            from_status=AmendmentBatchStatus.IN_REVIEW,
            to_status=target,
            actor_id=actor_id,
            note=(str(note).strip() if note else None),
            at=utc_now(),
        )


__all__ = ["AmendmentReviewService"]
