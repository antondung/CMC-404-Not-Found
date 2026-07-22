from __future__ import annotations

from typing import Any

from app.domain.amendment_commit import (
    AmendmentPostgresCommitState,
    AmendmentReconciliationIssue,
    AmendmentReconciliationReport,
)
from app.domain.amendment_review import AmendmentBatchStatus, utc_now


class AmendmentReconciliationService:
    """Read-only cross-store monitor for the Neo4j -> PostgreSQL commit saga."""

    def __init__(self, review_repository: Any, graph_repository: Any) -> None:
        self.review_repository = review_repository
        self.graph_repository = graph_repository

    async def check(self, *, limit: int = 200) -> AmendmentReconciliationReport:
        scan_limit = max(1, min(limit, 500))
        graph_evidence = await self.graph_repository.list_commit_evidence(
            limit=scan_limit
        )
        postgres_states = await self.review_repository.inspect_commit_reconciliation(
            graph_batch_ids=[item.batch_id for item in graph_evidence],
            limit=scan_limit,
        )
        state_by_batch = {item.batch_id: item for item in postgres_states}
        issues: list[AmendmentReconciliationIssue] = []
        issued_batches: set[str] = set()

        for evidence in graph_evidence:
            state = state_by_batch.get(evidence.batch_id)
            code: str | None = None
            if len(evidence.commit_keys) != 1:
                code = "graph_key_conflict"
            elif evidence.committed_at is None or len(evidence.committed_by) != 1:
                code = "graph_metadata_incomplete"
            elif state is None:
                code = "postgres_batch_missing"
            elif state.status != AmendmentBatchStatus.COMMITTED.value:
                code = "graph_commit_unreconciled"
            elif not state.metadata_complete:
                code = "postgres_metadata_incomplete"
            elif state.commit_idempotency_key != evidence.commit_keys[0]:
                code = "commit_key_mismatch"
            elif not state.reconciliation_event_present:
                code = "reconciliation_audit_missing"
            if code is not None:
                issues.append(self._issue(code, evidence.commit_keys, state, evidence.batch_id))
                issued_batches.add(evidence.batch_id)

        for state in postgres_states:
            if state.batch_id in issued_batches or state.status != AmendmentBatchStatus.COMMITTED.value:
                continue
            code = None
            if not state.metadata_complete:
                code = "postgres_metadata_incomplete"
            elif not state.reconciliation_event_present:
                code = "reconciliation_audit_missing"
            if code is not None:
                issues.append(self._issue(code, [], state, state.batch_id))

        return AmendmentReconciliationReport(
            status="degraded" if issues else "healthy",
            scanned_graph_commits=len(graph_evidence),
            issue_count=len(issues),
            issues=issues,
            checked_at=utc_now(),
        )

    @staticmethod
    def _issue(
        code: str,
        graph_keys: list[str],
        state: AmendmentPostgresCommitState | None,
        batch_id: str,
    ) -> AmendmentReconciliationIssue:
        return AmendmentReconciliationIssue(
            batch_id=batch_id,
            code=code,
            graph_commit_keys=graph_keys,
            postgres_status=state.status if state else None,
            postgres_commit_key=state.commit_idempotency_key if state else None,
        )


__all__ = ["AmendmentReconciliationService"]
