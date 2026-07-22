from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domain.amendment import LegalChangeType
from app.domain.amendment_commit import (
    AmendmentCommitOperation,
    AmendmentGraphCommitEvidence,
    AmendmentGraphCommitReport,
)
from app.exceptions import AmendmentCommitConflictError, AmendmentCommitUnavailableError


_PAIRED_QUERY = """
/* amendment_commit_paired */
MATCH (old:LegalProvision {provision_id: $old_id})
MATCH (new:LegalProvision {provision_id: $new_id})
MATCH (source:VanBanPhapLuat {vb_id: $source_vb_id})
OPTIONAL MATCH (old)-[prior:SUPERSEDED_BY]->(new)
OPTIONAL MATCH (old)-[amended_prior:AMENDED_BY]->(source)
WITH old, new, source, prior, amended_prior
WHERE old.text_checksum = $old_checksum
  AND new.text_checksum = $new_checksum
  AND old.lineage_id = $lineage_id AND new.lineage_id = $lineage_id
  AND old.level = $level AND new.level = $level
  AND date(old.effective_from) = date($old_effective_from)
  AND date(new.effective_from) = date($effective_from)
  AND new.source_vb_id = $source_vb_id
  AND (old.effective_to IS NULL OR date(old.effective_to) = date($effective_from))
  AND NOT EXISTS {
    MATCH (old)-[:SUPERSEDED_BY]->(other:LegalProvision)
    WHERE other.provision_id <> $new_id
  }
  AND NOT EXISTS {
    MATCH (other:LegalProvision)-[:SUPERSEDED_BY]->(new)
    WHERE other.provision_id <> $old_id
  }
  AND NOT EXISTS { MATCH (new)-[:SUPERSEDED_BY*1..]->(old) }
  AND (
    prior IS NULL OR (
      prior.review_id = $batch_id AND prior.commit_key = $idempotency_key
    )
  )
  AND (
    amended_prior IS NULL OR (
      amended_prior.review_id = $batch_id
      AND amended_prior.commit_key = $idempotency_key
    )
  )
WITH old, new, source, prior, amended_prior,
     prior IS NOT NULL AND amended_prior IS NOT NULL AS replay
SET old.effective_to = date($effective_from),
    new.review_status = 'approved'
MERGE (old)-[edge:SUPERSEDED_BY]->(new)
ON CREATE SET edge.effective_from = date($effective_from),
              edge.change_type = $change_type,
              edge.confidence = $confidence,
              edge.review_id = $batch_id,
              edge.source_vb_id = $source_vb_id,
              edge.commit_key = $idempotency_key,
              edge.committed_by = $actor_id,
              edge.committed_at = datetime($committed_at)
MERGE (old)-[amended:AMENDED_BY]->(source)
ON CREATE SET amended.review_id = $batch_id,
              amended.commit_key = $idempotency_key,
              amended.committed_by = $actor_id,
              amended.committed_at = datetime($committed_at)
RETURN replay, 1 AS superseded_edges, 1 AS closed_intervals, 1 AS approved_versions
"""


_ADDED_QUERY = """
/* amendment_commit_added */
MATCH (new:LegalProvision {provision_id: $new_id})
MATCH (source:VanBanPhapLuat {vb_id: $source_vb_id})
OPTIONAL MATCH (new)-[prior:AMENDED_BY]->(source)
WITH new, source, prior
WHERE new.text_checksum = $new_checksum
  AND new.lineage_id = $lineage_id
  AND new.level = $level
  AND date(new.effective_from) = date($effective_from)
  AND new.source_vb_id = $source_vb_id
  AND (
    prior IS NULL OR (
      prior.review_id = $batch_id AND prior.commit_key = $idempotency_key
    )
  )
WITH new, source, prior, prior IS NOT NULL AS replay
SET new.review_status = 'approved'
MERGE (new)-[amended:AMENDED_BY]->(source)
ON CREATE SET amended.review_id = $batch_id,
              amended.commit_key = $idempotency_key,
              amended.committed_by = $actor_id,
              amended.committed_at = datetime($committed_at)
RETURN replay, 0 AS superseded_edges, 0 AS closed_intervals, 1 AS approved_versions
"""


_REMOVED_QUERY = """
/* amendment_commit_removed */
MATCH (old:LegalProvision {provision_id: $old_id})
MATCH (source:VanBanPhapLuat {vb_id: $source_vb_id})
OPTIONAL MATCH (old)-[prior:AMENDED_BY]->(source)
WITH old, source, prior
WHERE old.text_checksum = $old_checksum
  AND old.lineage_id = $lineage_id
  AND old.level = $level
  AND date(old.effective_from) = date($old_effective_from)
  AND (old.effective_to IS NULL OR date(old.effective_to) = date($effective_from))
  AND NOT EXISTS { MATCH (old)-[:SUPERSEDED_BY]->(:LegalProvision) }
  AND (
    prior IS NULL OR (
      prior.review_id = $batch_id AND prior.commit_key = $idempotency_key
    )
  )
WITH old, source, prior, prior IS NOT NULL AS replay
SET old.effective_to = date($effective_from)
MERGE (old)-[amended:AMENDED_BY]->(source)
ON CREATE SET amended.review_id = $batch_id,
              amended.commit_key = $idempotency_key,
              amended.committed_by = $actor_id,
              amended.committed_at = datetime($committed_at)
RETURN replay, 0 AS superseded_edges, 1 AS closed_intervals, 0 AS approved_versions
"""


_RECONCILIATION_EVIDENCE_QUERY = """
/* amendment_commit_reconciliation_evidence */
MATCH ()-[edge:AMENDED_BY]->()
WHERE edge.review_id IS NOT NULL AND edge.commit_key IS NOT NULL
WITH toString(edge.review_id) AS batch_id,
     collect(DISTINCT toString(edge.commit_key)) AS commit_keys,
     collect(DISTINCT toString(edge['committed_by'])) AS committed_by,
     min(edge['committed_at']) AS committed_at,
     count(edge) AS edge_count
RETURN batch_id, commit_keys, committed_by, committed_at, edge_count
ORDER BY committed_at DESC, batch_id
LIMIT $limit
"""


def _record_data(record: Any) -> dict[str, Any]:
    data = getattr(record, "data", None)
    return data() if callable(data) else dict(record)


def _native_datetime(value: Any) -> Any:
    to_native = getattr(value, "to_native", None)
    return to_native() if callable(to_native) else value


class Neo4jAmendmentCommitRepository:
    """The only adapter allowed to close legal intervals and create temporal edges."""

    def __init__(self, driver: Any) -> None:
        self.driver = driver

    async def list_commit_evidence(
        self,
        *,
        limit: int = 200,
    ) -> list[AmendmentGraphCommitEvidence]:
        """Read recent graph commit stamps without mutating canonical legal data."""
        if not (self.driver and hasattr(self.driver, "session")):
            raise AmendmentCommitUnavailableError("Neo4j amendment commit is unavailable")
        try:
            async with self.driver.session(default_access_mode="READ") as session:
                execute_read = getattr(session, "execute_read", None)
                if execute_read is None:
                    raise AmendmentCommitUnavailableError(
                        "Neo4j managed read transactions are unavailable"
                    )
                return await execute_read(self._list_commit_evidence_tx, limit)
        except AmendmentCommitUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AmendmentCommitUnavailableError(
                "Neo4j amendment reconciliation scan failed",
                details={"error_type": type(exc).__name__},
            ) from exc

    @staticmethod
    async def _list_commit_evidence_tx(
        tx: Any,
        limit: int,
    ) -> list[AmendmentGraphCommitEvidence]:
        result = await tx.run(_RECONCILIATION_EVIDENCE_QUERY, limit=max(1, min(limit, 500)))
        evidence: list[AmendmentGraphCommitEvidence] = []
        async for record in result:
            row = _record_data(record)
            evidence.append(
                AmendmentGraphCommitEvidence(
                    batch_id=str(row["batch_id"]),
                    commit_keys=sorted(str(key) for key in row.get("commit_keys") or []),
                    committed_by=sorted(
                        str(actor) for actor in row.get("committed_by") or []
                    ),
                    committed_at=_native_datetime(row.get("committed_at")),
                    edge_count=int(row.get("edge_count") or 0),
                )
            )
        return evidence

    async def commit(
        self,
        *,
        batch_id: str,
        idempotency_key: str,
        amending_source_vb_id: str,
        operations: list[AmendmentCommitOperation],
        actor_id: str,
        committed_at: datetime,
    ) -> AmendmentGraphCommitReport:
        if not operations:
            raise AmendmentCommitConflictError("amendment commit has no accepted operations")
        if not (self.driver and hasattr(self.driver, "session")):
            raise AmendmentCommitUnavailableError("Neo4j amendment commit is unavailable")
        try:
            async with self.driver.session() as session:
                execute_write = getattr(session, "execute_write", None)
                if execute_write is None:
                    raise AmendmentCommitUnavailableError(
                        "Neo4j managed write transactions are unavailable"
                    )
                return await execute_write(
                    self._commit_transaction,
                    batch_id,
                    idempotency_key,
                    amending_source_vb_id,
                    operations,
                    actor_id,
                    committed_at,
                )
        except (AmendmentCommitConflictError, AmendmentCommitUnavailableError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise AmendmentCommitUnavailableError(
                "Neo4j amendment transaction failed",
                details={"error_type": type(exc).__name__},
            ) from exc

    @staticmethod
    async def _commit_transaction(
        tx: Any,
        batch_id: str,
        idempotency_key: str,
        amending_source_vb_id: str,
        operations: list[AmendmentCommitOperation],
        actor_id: str,
        committed_at: datetime,
    ) -> AmendmentGraphCommitReport:
        totals = {
            "superseded_edges": 0,
            "closed_intervals": 0,
            "approved_versions": 0,
        }
        replay_flags: list[bool] = []
        for operation in operations:
            old = operation.old_version
            new = operation.new_version
            if old is not None and new is not None:
                query = _PAIRED_QUERY
            elif new is not None:
                query = _ADDED_QUERY
            else:
                query = _REMOVED_QUERY
            anchor = old or new
            assert anchor is not None
            result = await tx.run(
                query,
                batch_id=batch_id,
                idempotency_key=idempotency_key,
                source_vb_id=amending_source_vb_id,
                candidate_id=operation.candidate_id,
                old_id=old.provision_id if old else None,
                new_id=new.provision_id if new else None,
                old_checksum=old.text_checksum if old else None,
                new_checksum=new.text_checksum if new else None,
                lineage_id=anchor.lineage_id,
                level=anchor.level.value,
                old_effective_from=old.effective_from.isoformat() if old else None,
                effective_from=operation.proposed_effective_from.isoformat(),
                change_type=operation.change_type.value,
                confidence=operation.confidence,
                actor_id=actor_id,
                committed_at=committed_at.isoformat(),
            )
            rows = [_record_data(record) async for record in result]
            if len(rows) != 1:
                raise AmendmentCommitConflictError(
                    "canonical graph state no longer matches the approved amendment",
                    details={
                        "batch_id": batch_id,
                        "candidate_id": operation.candidate_id,
                        "matched_rows": len(rows),
                    },
                )
            row = rows[0]
            replay_flags.append(bool(row.get("replay")))
            for key in totals:
                totals[key] += int(row.get(key) or 0)
        return AmendmentGraphCommitReport(
            batch_id=batch_id,
            idempotency_key=idempotency_key,
            amending_source_vb_id=amending_source_vb_id,
            committed_candidate_ids=[item.candidate_id for item in operations],
            superseded_edges=totals["superseded_edges"],
            closed_intervals=totals["closed_intervals"],
            approved_versions=totals["approved_versions"],
            idempotent_replay=all(replay_flags),
            committed_by=actor_id,
            committed_at=committed_at,
            graph_mutated=not all(replay_flags),
        )


__all__ = ["Neo4jAmendmentCommitRepository"]
