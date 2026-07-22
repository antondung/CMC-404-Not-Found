from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from app.domain.amendment import (
    AmendmentDiffHunk,
    AmendmentReviewRoute,
    AmendmentScoreBreakdown,
    LegalChangeType,
)
from app.domain.amendment_review import (
    AmendmentBatchStatus,
    AmendmentCandidateDecision,
    AmendmentReviewBatch,
    AmendmentReviewBatchSummary,
    AmendmentReviewCandidate,
)
from app.domain.amendment_commit import AmendmentPostgresCommitState
from app.exceptions import (
    AmendmentReviewConflictError,
    AmendmentReviewNotFoundError,
    AmendmentReviewPersistenceError,
    BE2Error,
)


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def _row_dict(row: Any) -> dict[str, Any]:
    return dict(row) if row is not None else {}


class PostgresAmendmentReviewRepository:
    """PostgreSQL persistence for review-only amendment proposals and audit events."""

    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def inspect_commit_reconciliation(
        self,
        *,
        graph_batch_ids: list[str],
        limit: int = 200,
    ) -> list[AmendmentPostgresCommitState]:
        """Return matching batches plus any committed row with incomplete evidence."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    WITH reconciliation_state AS (
                      SELECT batch.id::text AS batch_id,
                             batch.status::text AS status,
                             batch.commit_idempotency_key,
                             batch.committed_by,
                             batch.committed_at,
                             batch.commit_result IS NOT NULL AS commit_result_present,
                             EXISTS (
                               SELECT 1 FROM amendment_review_events event
                               WHERE event.batch_id = batch.id
                                 AND event.action = 'graph_commit_reconciled'
                             ) AS reconciliation_event_present,
                             batch.updated_at
                      FROM amendment_review_batches batch
                    )
                    SELECT batch_id, status, commit_idempotency_key, committed_by,
                           committed_at, commit_result_present,
                           reconciliation_event_present
                    FROM reconciliation_state
                    WHERE batch_id = ANY($1::text[])
                       OR (
                         status = 'committed' AND (
                           commit_idempotency_key IS NULL
                           OR committed_by IS NULL
                           OR committed_at IS NULL
                           OR NOT commit_result_present
                           OR NOT reconciliation_event_present
                         )
                       )
                    ORDER BY updated_at DESC, batch_id
                    LIMIT $2
                    """,
                    list(dict.fromkeys(graph_batch_ids)),
                    max(1, min(limit, 500)),
                )
            return [
                AmendmentPostgresCommitState(
                    batch_id=str(row["batch_id"]),
                    status=str(row["status"]),
                    commit_idempotency_key=row.get("commit_idempotency_key"),
                    committed_by=row.get("committed_by"),
                    committed_at=row.get("committed_at"),
                    commit_result_present=bool(row.get("commit_result_present")),
                    reconciliation_event_present=bool(
                        row.get("reconciliation_event_present")
                    ),
                )
                for row in rows
            ]
        except BE2Error:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AmendmentReviewPersistenceError(
                "failed to inspect amendment commit reconciliation",
                details={"error_type": type(exc).__name__},
            ) from exc

    @staticmethod
    def _candidate_from_row(row: Any) -> AmendmentReviewCandidate:
        data = _row_dict(row)
        score_raw = _json_value(data.get("score_breakdown"), None)
        diff_raw = _json_value(data.get("diff_hunks"), [])
        return AmendmentReviewCandidate(
            candidate_id=str(data["candidate_id"]),
            batch_id=str(data["batch_id"]),
            old_provision_id=data.get("old_provision_id"),
            new_provision_id=data.get("new_provision_id"),
            lineage_id=data.get("lineage_id"),
            reference_ids=list(_json_value(data.get("reference_ids"), [])),
            confidence=float(data.get("confidence") or 0),
            score=AmendmentScoreBreakdown.model_validate(score_raw) if score_raw else None,
            change_type=LegalChangeType(str(data["change_type"])),
            review_route=AmendmentReviewRoute(str(data["review_route"])),
            proposed_effective_from=data.get("proposed_effective_from"),
            decision=AmendmentCandidateDecision(str(data.get("decision") or "pending")),
            reason_codes=list(_json_value(data.get("reason_codes"), [])),
            diff_hunks=[AmendmentDiffHunk.model_validate(item) for item in diff_raw],
            reviewer_note=data.get("reviewer_note"),
            reviewed_by=data.get("reviewed_by"),
            reviewed_at=data.get("reviewed_at"),
            revision=int(data.get("revision") or 1),
            commit_allowed=False,
            auto_approve_eligible=False,
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    @staticmethod
    def _batch_from_rows(batch_row: Any, candidate_rows: list[Any]) -> AmendmentReviewBatch:
        data = _row_dict(batch_row)
        return AmendmentReviewBatch(
            batch_id=str(data["batch_id"]),
            target_logical_vb_id=str(data["target_logical_vb_id"]),
            amendment_text=str(data["amendment_text"]),
            status=AmendmentBatchStatus(str(data["status"])),
            idempotency_key=str(data["idempotency_key"]),
            request_hash=str(data["request_hash"]),
            preview_snapshot=dict(_json_value(data.get("preview_snapshot"), {})),
            candidates=[
                PostgresAmendmentReviewRepository._candidate_from_row(row)
                for row in candidate_rows
            ],
            created_by=str(data["created_by"]),
            submitted_by=data.get("submitted_by"),
            submitted_at=data.get("submitted_at"),
            reviewed_by=data.get("reviewed_by"),
            reviewed_at=data.get("reviewed_at"),
            review_note=data.get("review_note"),
            commit_idempotency_key=data.get("commit_idempotency_key"),
            committed_by=data.get("committed_by"),
            committed_at=data.get("committed_at"),
            commit_result=(
                dict(_json_value(data.get("commit_result"), {}))
                if data.get("commit_result") is not None
                else None
            ),
            revision=int(data.get("revision") or 1),
            commit_allowed=False,
            auto_approve_eligible=False,
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    @staticmethod
    async def _load_batch_with_conn(conn: Any, batch_id: str) -> AmendmentReviewBatch | None:
        batch_row = await conn.fetchrow(
            """
            SELECT id::text AS batch_id, target_logical_vb_id, amendment_text,
                   status::text AS status, idempotency_key, request_hash,
                   preview_snapshot, created_by, submitted_by, submitted_at,
                   reviewed_by, reviewed_at, review_note, revision,
                   commit_idempotency_key, committed_by, committed_at, commit_result,
                   created_at, updated_at
            FROM amendment_review_batches
            WHERE id = $1::uuid
            """,
            batch_id,
        )
        if batch_row is None:
            return None
        candidate_rows = await conn.fetch(
            """
            SELECT id::text AS candidate_id, batch_id::text AS batch_id,
                   old_provision_id, new_provision_id, lineage_id, reference_ids,
                   confidence, score_breakdown, change_type, review_route,
                   proposed_effective_from, decision::text AS decision,
                   reason_codes, diff_hunks, reviewer_note, reviewed_by,
                   reviewed_at, revision, created_at, updated_at
            FROM amendment_review_candidates
            WHERE batch_id = $1::uuid
            ORDER BY created_at, id
            """,
            batch_id,
        )
        return PostgresAmendmentReviewRepository._batch_from_rows(
            batch_row, list(candidate_rows)
        )

    async def create_batch(
        self,
        batch: AmendmentReviewBatch,
    ) -> tuple[AmendmentReviewBatch, bool]:
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        """
                        INSERT INTO amendment_review_batches (
                          id, target_logical_vb_id, amendment_text, status,
                          idempotency_key, request_hash, preview_snapshot,
                          created_by, revision, commit_allowed,
                          auto_approve_eligible, created_at, updated_at
                        ) VALUES (
                          $1::uuid, $2, $3, $4::amendment_batch_status,
                          $5, $6, $7::jsonb, $8, 1, FALSE, FALSE, $9, $9
                        )
                        ON CONFLICT (idempotency_key) DO NOTHING
                        RETURNING id::text AS batch_id
                        """,
                        batch.batch_id,
                        batch.target_logical_vb_id,
                        batch.amendment_text,
                        batch.status.value,
                        batch.idempotency_key,
                        batch.request_hash,
                        json.dumps(batch.preview_snapshot, ensure_ascii=False),
                        batch.created_by,
                        batch.created_at,
                    )
                    if row is None:
                        existing = await conn.fetchrow(
                            """
                            SELECT id::text AS batch_id, request_hash
                            FROM amendment_review_batches
                            WHERE idempotency_key = $1
                            """,
                            batch.idempotency_key,
                        )
                        if existing is None:
                            raise AmendmentReviewPersistenceError(
                                "idempotent amendment batch could not be resolved"
                            )
                        if str(existing["request_hash"]) != batch.request_hash:
                            raise AmendmentReviewConflictError(
                                "idempotency key was already used for another amendment request",
                                details={"idempotency_key": batch.idempotency_key},
                            )
                        loaded = await self._load_batch_with_conn(
                            conn, str(existing["batch_id"])
                        )
                        if loaded is None:
                            raise AmendmentReviewPersistenceError(
                                "existing amendment batch disappeared during read"
                            )
                        return loaded, False

                    for candidate in batch.candidates:
                        await conn.execute(
                            """
                            INSERT INTO amendment_review_candidates (
                              id, batch_id, old_provision_id, new_provision_id,
                              lineage_id, reference_ids, confidence, score_breakdown,
                              change_type, review_route, proposed_effective_from,
                              decision, reason_codes, diff_hunks, revision,
                              commit_allowed, auto_approve_eligible,
                              created_at, updated_at
                            ) VALUES (
                              $1::uuid, $2::uuid, $3, $4, $5, $6::jsonb, $7,
                              $8::jsonb, $9, $10, $11, 'pending', $12::jsonb,
                              $13::jsonb, 1, FALSE, FALSE, $14, $14
                            )
                            """,
                            candidate.candidate_id,
                            batch.batch_id,
                            candidate.old_provision_id,
                            candidate.new_provision_id,
                            candidate.lineage_id,
                            json.dumps(candidate.reference_ids, ensure_ascii=False),
                            candidate.confidence,
                            json.dumps(
                                candidate.score.model_dump(mode="json")
                                if candidate.score
                                else None,
                                ensure_ascii=False,
                            ),
                            candidate.change_type.value,
                            candidate.review_route.value,
                            candidate.proposed_effective_from,
                            json.dumps(candidate.reason_codes, ensure_ascii=False),
                            json.dumps(
                                [item.model_dump(mode="json") for item in candidate.diff_hunks],
                                ensure_ascii=False,
                            ),
                            candidate.created_at,
                        )
                    await conn.execute(
                        """
                        INSERT INTO amendment_review_events (
                          batch_id, actor_id, action, to_status,
                          expected_revision, payload
                        ) VALUES ($1::uuid, $2, 'batch_created', 'draft', 0, $3::jsonb)
                        """,
                        batch.batch_id,
                        batch.created_by,
                        json.dumps(
                            {"request_hash": batch.request_hash, "candidate_count": len(batch.candidates)},
                            ensure_ascii=False,
                        ),
                    )
                    loaded = await self._load_batch_with_conn(conn, batch.batch_id)
                    if loaded is None:
                        raise AmendmentReviewPersistenceError(
                            "created amendment batch could not be loaded"
                        )
                    return loaded, True
        except BE2Error:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AmendmentReviewPersistenceError(
                "failed to persist amendment review batch",
                details={"error_type": type(exc).__name__},
            ) from exc

    async def get_batch(self, batch_id: str) -> AmendmentReviewBatch:
        try:
            async with self.pool.acquire() as conn:
                loaded = await self._load_batch_with_conn(conn, batch_id)
            if loaded is None:
                raise AmendmentReviewNotFoundError(
                    "amendment review batch not found", details={"batch_id": batch_id}
                )
            return loaded
        except BE2Error:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AmendmentReviewPersistenceError(
                "failed to load amendment review batch",
                details={"error_type": type(exc).__name__},
            ) from exc

    async def list_batches(
        self,
        *,
        status: AmendmentBatchStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AmendmentReviewBatchSummary], int]:
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT b.id::text AS batch_id, b.target_logical_vb_id,
                           b.status::text AS status, b.revision, b.created_by,
                           b.created_at, b.updated_at,
                           count(c.id)::int AS candidate_count,
                           count(c.id) FILTER (WHERE c.decision = 'pending')::int AS pending_count
                    FROM amendment_review_batches b
                    LEFT JOIN amendment_review_candidates c ON c.batch_id = b.id
                    WHERE ($1::text IS NULL OR b.status::text = $1)
                    GROUP BY b.id
                    ORDER BY b.updated_at DESC, b.id
                    LIMIT $2 OFFSET $3
                    """,
                    status.value if status else None,
                    limit,
                    offset,
                )
                total = await conn.fetchval(
                    """
                    SELECT count(*)::int
                    FROM amendment_review_batches
                    WHERE ($1::text IS NULL OR status::text = $1)
                    """,
                    status.value if status else None,
                )
            items = [
                AmendmentReviewBatchSummary(
                    **_row_dict(row), commit_allowed=False
                )
                for row in rows
            ]
            return items, int(total or 0)
        except Exception as exc:  # noqa: BLE001
            raise AmendmentReviewPersistenceError(
                "failed to list amendment review batches",
                details={"error_type": type(exc).__name__},
            ) from exc

    async def update_candidate(
        self,
        candidate: AmendmentReviewCandidate,
        *,
        expected_revision: int,
        actor_id: str,
    ) -> AmendmentReviewCandidate:
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        """
                        UPDATE amendment_review_candidates
                        SET old_provision_id = $4,
                            new_provision_id = $5,
                            lineage_id = $6,
                            reference_ids = $7::jsonb,
                            confidence = $8,
                            score_breakdown = $9::jsonb,
                            change_type = $10,
                            proposed_effective_from = $11,
                            decision = $12::amendment_candidate_decision,
                            reason_codes = $13::jsonb,
                            diff_hunks = $14::jsonb,
                            reviewer_note = $15,
                            reviewed_by = $16,
                            reviewed_at = $17,
                            review_route = $18,
                            revision = revision + 1
                        WHERE id = $1::uuid AND batch_id = $2::uuid
                          AND revision = $3
                        RETURNING id::text AS candidate_id
                        """,
                        candidate.candidate_id,
                        candidate.batch_id,
                        expected_revision,
                        candidate.old_provision_id,
                        candidate.new_provision_id,
                        candidate.lineage_id,
                        json.dumps(candidate.reference_ids, ensure_ascii=False),
                        candidate.confidence,
                        json.dumps(
                            candidate.score.model_dump(mode="json")
                            if candidate.score
                            else None,
                            ensure_ascii=False,
                        ),
                        candidate.change_type.value,
                        candidate.proposed_effective_from,
                        candidate.decision.value,
                        json.dumps(candidate.reason_codes, ensure_ascii=False),
                        json.dumps(
                            [item.model_dump(mode="json") for item in candidate.diff_hunks],
                            ensure_ascii=False,
                        ),
                        candidate.reviewer_note,
                        candidate.reviewed_by,
                        candidate.reviewed_at,
                        candidate.review_route.value,
                    )
                    if row is None:
                        current = await conn.fetchrow(
                            """
                            SELECT revision FROM amendment_review_candidates
                            WHERE id = $1::uuid AND batch_id = $2::uuid
                            """,
                            candidate.candidate_id,
                            candidate.batch_id,
                        )
                        if current is None:
                            raise AmendmentReviewNotFoundError(
                                "amendment review candidate not found",
                                details={"candidate_id": candidate.candidate_id},
                            )
                        raise AmendmentReviewConflictError(
                            "amendment candidate revision conflict",
                            details={
                                "candidate_id": candidate.candidate_id,
                                "expected_revision": expected_revision,
                                "current_revision": int(current["revision"]),
                            },
                        )
                    await conn.execute(
                        """
                        INSERT INTO amendment_review_events (
                          batch_id, candidate_id, actor_id, action,
                          expected_revision, payload
                        ) VALUES ($1::uuid, $2::uuid, $3, 'candidate_updated', $4, $5::jsonb)
                        """,
                        candidate.batch_id,
                        candidate.candidate_id,
                        actor_id,
                        expected_revision,
                        json.dumps(
                            {
                                "decision": candidate.decision.value,
                                "change_type": candidate.change_type.value,
                                "proposed_effective_from": (
                                    candidate.proposed_effective_from.isoformat()
                                    if candidate.proposed_effective_from
                                    else None
                                ),
                            },
                            ensure_ascii=False,
                        ),
                    )
                    updated = await conn.fetchrow(
                        """
                        SELECT id::text AS candidate_id, batch_id::text AS batch_id,
                               old_provision_id, new_provision_id, lineage_id,
                               reference_ids, confidence, score_breakdown, change_type,
                               review_route, proposed_effective_from,
                               decision::text AS decision, reason_codes, diff_hunks,
                               reviewer_note, reviewed_by, reviewed_at, revision,
                               created_at, updated_at
                        FROM amendment_review_candidates
                        WHERE id = $1::uuid
                        """,
                        candidate.candidate_id,
                    )
                    if updated is None:
                        raise AmendmentReviewPersistenceError(
                            "updated amendment candidate could not be loaded"
                        )
                    return self._candidate_from_row(updated)
        except BE2Error:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AmendmentReviewPersistenceError(
                "failed to update amendment review candidate",
                details={"error_type": type(exc).__name__},
            ) from exc

    async def transition_batch(
        self,
        *,
        batch_id: str,
        expected_revision: int,
        from_status: AmendmentBatchStatus,
        to_status: AmendmentBatchStatus,
        actor_id: str,
        note: str | None,
        at: datetime,
    ) -> AmendmentReviewBatch:
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        """
                        UPDATE amendment_review_batches
                        SET status = $4::amendment_batch_status,
                            submitted_by = CASE WHEN $4 = 'in_review' THEN $5 ELSE submitted_by END,
                            submitted_at = CASE WHEN $4 = 'in_review' THEN $7 ELSE submitted_at END,
                            reviewed_by = CASE WHEN $4 IN ('approved', 'rejected') THEN $5 ELSE reviewed_by END,
                            reviewed_at = CASE WHEN $4 IN ('approved', 'rejected') THEN $7 ELSE reviewed_at END,
                            review_note = CASE WHEN $4 IN ('approved', 'rejected') THEN $6 ELSE review_note END,
                            revision = revision + 1
                        WHERE id = $1::uuid AND revision = $2
                          AND status = $3::amendment_batch_status
                        RETURNING id::text AS batch_id
                        """,
                        batch_id,
                        expected_revision,
                        from_status.value,
                        to_status.value,
                        actor_id,
                        note,
                        at,
                    )
                    if row is None:
                        current = await conn.fetchrow(
                            """
                            SELECT status::text AS status, revision
                            FROM amendment_review_batches WHERE id = $1::uuid
                            """,
                            batch_id,
                        )
                        if current is None:
                            raise AmendmentReviewNotFoundError(
                                "amendment review batch not found",
                                details={"batch_id": batch_id},
                            )
                        raise AmendmentReviewConflictError(
                            "amendment review batch state or revision conflict",
                            details={
                                "batch_id": batch_id,
                                "expected_status": from_status.value,
                                "current_status": str(current["status"]),
                                "expected_revision": expected_revision,
                                "current_revision": int(current["revision"]),
                            },
                        )
                    await conn.execute(
                        """
                        INSERT INTO amendment_review_events (
                          batch_id, actor_id, action, from_status, to_status,
                          expected_revision, payload
                        ) VALUES ($1::uuid, $2, 'batch_transition', $3, $4, $5, $6::jsonb)
                        """,
                        batch_id,
                        actor_id,
                        from_status.value,
                        to_status.value,
                        expected_revision,
                        json.dumps({"note": note}, ensure_ascii=False),
                    )
                    loaded = await self._load_batch_with_conn(conn, batch_id)
                    if loaded is None:
                        raise AmendmentReviewPersistenceError(
                            "transitioned amendment batch could not be loaded"
                        )
                    return loaded
        except BE2Error:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AmendmentReviewPersistenceError(
                "failed to transition amendment review batch",
                details={"error_type": type(exc).__name__},
            ) from exc

    async def mark_committed(
        self,
        *,
        batch_id: str,
        expected_revision: int,
        idempotency_key: str,
        actor_id: str,
        commit_result: dict[str, Any],
        at: datetime,
    ) -> tuple[AmendmentReviewBatch, bool]:
        """Reconcile a successful idempotent Neo4j transaction into PostgreSQL."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    current = await conn.fetchrow(
                        """
                        SELECT status::text AS status, revision, commit_idempotency_key
                        FROM amendment_review_batches WHERE id = $1::uuid
                        """,
                        batch_id,
                    )
                    if current is None:
                        raise AmendmentReviewNotFoundError(
                            "amendment review batch not found",
                            details={"batch_id": batch_id},
                        )
                    key_owner = await conn.fetchrow(
                        """
                        SELECT id::text AS batch_id
                        FROM amendment_review_batches
                        WHERE commit_idempotency_key = $1 AND id <> $2::uuid
                        """,
                        idempotency_key,
                        batch_id,
                    )
                    if key_owner is not None:
                        raise AmendmentReviewConflictError(
                            "commit idempotency key belongs to another amendment batch",
                            details={
                                "idempotency_key": idempotency_key,
                                "batch_id": str(key_owner["batch_id"]),
                            },
                        )
                    if str(current["status"]) == AmendmentBatchStatus.COMMITTED.value:
                        if current["commit_idempotency_key"] != idempotency_key:
                            raise AmendmentReviewConflictError(
                                "amendment batch was committed with another idempotency key",
                                details={"batch_id": batch_id},
                            )
                        loaded = await self._load_batch_with_conn(conn, batch_id)
                        if loaded is None:
                            raise AmendmentReviewPersistenceError(
                                "committed amendment batch could not be loaded"
                            )
                        return loaded, False
                    if (
                        str(current["status"]) != AmendmentBatchStatus.APPROVED.value
                        or int(current["revision"]) != expected_revision
                    ):
                        raise AmendmentReviewConflictError(
                            "amendment commit state or revision conflict",
                            details={
                                "batch_id": batch_id,
                                "current_status": str(current["status"]),
                                "current_revision": int(current["revision"]),
                                "expected_revision": expected_revision,
                            },
                        )
                    row = await conn.fetchrow(
                        """
                        UPDATE amendment_review_batches
                        SET status = 'committed'::amendment_batch_status,
                            commit_idempotency_key = $3,
                            committed_by = $4,
                            committed_at = $5,
                            commit_result = $6::jsonb,
                            revision = revision + 1
                        WHERE id = $1::uuid AND revision = $2
                          AND status = 'approved'::amendment_batch_status
                        RETURNING id::text AS batch_id
                        """,
                        batch_id,
                        expected_revision,
                        idempotency_key,
                        actor_id,
                        at,
                        json.dumps(commit_result, ensure_ascii=False),
                    )
                    if row is None:
                        raise AmendmentReviewConflictError(
                            "amendment commit lost an optimistic concurrency race",
                            details={"batch_id": batch_id},
                        )
                    await conn.execute(
                        """
                        INSERT INTO amendment_review_events (
                          batch_id, actor_id, action, from_status, to_status,
                          expected_revision, payload
                        ) VALUES (
                          $1::uuid, $2, 'graph_commit_reconciled', 'approved',
                          'committed', $3, $4::jsonb
                        )
                        """,
                        batch_id,
                        actor_id,
                        expected_revision,
                        json.dumps(
                            {
                                "idempotency_key": idempotency_key,
                                "commit_result": commit_result,
                            },
                            ensure_ascii=False,
                        ),
                    )
                    loaded = await self._load_batch_with_conn(conn, batch_id)
                    if loaded is None:
                        raise AmendmentReviewPersistenceError(
                            "reconciled amendment batch could not be loaded"
                        )
                    return loaded, True
        except BE2Error:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AmendmentReviewPersistenceError(
                "failed to reconcile amendment graph commit",
                details={"error_type": type(exc).__name__},
            ) from exc


__all__ = ["PostgresAmendmentReviewRepository"]
