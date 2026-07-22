from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.evaluation.acceptance_catalog import (
    EXPECTED_ACCEPTANCE_IDS,
    assert_rows,
    load_acceptance_catalog,
)
from app.evaluation.lawgic_quality import EvaluationError
from app.pipelines.legal.provision_index import (
    LEGAL_PROVISION_COLLECTION,
    load_leaf_provisions_from_neo4j,
)
from app.services.legal_shadow_parity import build_shadow_parity_report


@dataclass(frozen=True)
class PostgresAcceptanceCheck:
    check_id: str
    title: str
    query: str


POSTGRES_ACCEPTANCE_CHECKS: tuple[PostgresAcceptanceCheck, ...] = (
    PostgresAcceptanceCheck(
        "PG01",
        "Required amendment review and reconciliation columns exist",
        """
        WITH required(table_name, column_name) AS (
          VALUES
            ('amendment_review_batches', 'commit_allowed'),
            ('amendment_review_batches', 'auto_approve_eligible'),
            ('amendment_review_batches', 'commit_idempotency_key'),
            ('amendment_review_batches', 'committed_by'),
            ('amendment_review_batches', 'committed_at'),
            ('amendment_review_batches', 'commit_result'),
            ('amendment_review_candidates', 'commit_allowed'),
            ('amendment_review_candidates', 'auto_approve_eligible'),
            ('amendment_review_events', 'action')
        )
        SELECT required.table_name, required.column_name
        FROM required
        LEFT JOIN information_schema.columns actual
          ON actual.table_schema = 'public'
         AND actual.table_name = required.table_name
         AND actual.column_name = required.column_name
        WHERE actual.column_name IS NULL
        ORDER BY required.table_name, required.column_name
        """,
    ),
    PostgresAcceptanceCheck(
        "PG02",
        "Review persistence never enables auto approval or direct commit",
        """
        SELECT 'batch' AS record_type, id::text AS record_id
        FROM amendment_review_batches
        WHERE commit_allowed IS TRUE OR auto_approve_eligible IS TRUE
        UNION ALL
        SELECT 'candidate' AS record_type, id::text AS record_id
        FROM amendment_review_candidates
        WHERE commit_allowed IS TRUE OR auto_approve_eligible IS TRUE
        """,
    ),
    PostgresAcceptanceCheck(
        "PG03",
        "Committed batches have complete retry-safe reconciliation evidence",
        """
        SELECT id::text AS batch_id
        FROM amendment_review_batches
        WHERE status::text = 'committed'
          AND (
            commit_idempotency_key IS NULL
            OR committed_by IS NULL
            OR committed_at IS NULL
            OR commit_result IS NULL
            OR jsonb_typeof(commit_result) <> 'object'
          )
        """,
    ),
    PostgresAcceptanceCheck(
        "PG04",
        "Reviewed terminal batches retain actor and timestamp",
        """
        SELECT id::text AS batch_id, status::text AS status
        FROM amendment_review_batches
        WHERE status::text IN ('approved', 'rejected', 'committed')
          AND (reviewed_by IS NULL OR reviewed_at IS NULL)
        """,
    ),
    PostgresAcceptanceCheck(
        "PG05",
        "Candidates and audit events are attached to existing review batches",
        """
        SELECT 'candidate' AS record_type, candidate.id::text AS record_id
        FROM amendment_review_candidates candidate
        LEFT JOIN amendment_review_batches batch ON batch.id = candidate.batch_id
        WHERE batch.id IS NULL
        UNION ALL
        SELECT 'event' AS record_type, event.id::text AS record_id
        FROM amendment_review_events event
        LEFT JOIN amendment_review_batches batch ON batch.id = event.batch_id
        WHERE batch.id IS NULL
        """,
    ),
    PostgresAcceptanceCheck(
        "PG06",
        "Every non-draft workflow has an append-only audit event",
        """
        SELECT batch.id::text AS batch_id, batch.status::text AS status
        FROM amendment_review_batches batch
        WHERE batch.status::text <> 'draft'
          AND NOT EXISTS (
            SELECT 1 FROM amendment_review_events event
            WHERE event.batch_id = batch.id
          )
        """,
    ),
    PostgresAcceptanceCheck(
        "PG07",
        "The fixture amendment is durably reviewed, committed and audited",
        """
        SELECT $1::uuid AS missing_fixture_review_id
        WHERE NOT EXISTS (
          SELECT 1
          FROM amendment_review_batches batch
          WHERE batch.id = $1::uuid
            AND batch.status::text = 'committed'
            AND batch.reviewed_by IS NOT NULL
            AND batch.reviewed_at IS NOT NULL
            AND batch.commit_idempotency_key IS NOT NULL
            AND batch.committed_by IS NOT NULL
            AND batch.committed_at IS NOT NULL
            AND jsonb_typeof(batch.commit_result) = 'object'
            AND EXISTS (
              SELECT 1 FROM amendment_review_events event
              WHERE event.batch_id = batch.id AND event.action = 'graph_commit_reconciled'
            )
        )
        """,
    ),
)

_NEGATIVE_NEO4J_CHECKS = {"T09", "T10", "T17", "N02", "T19", "T20"}


def _placeholder_path(value: Any, path: str = "config") -> str | None:
    if isinstance(value, str) and "REPLACE" in value.upper():
        return path
    if isinstance(value, Mapping):
        for key, item in value.items():
            found = _placeholder_path(item, f"{path}.{key}")
            if found:
                return found
    if isinstance(value, list):
        for index, item in enumerate(value):
            found = _placeholder_path(item, f"{path}[{index}]")
            if found:
                return found
    return None


def validate_integration_config(config: Mapping[str, Any]) -> None:
    placeholder = _placeholder_path(config)
    if placeholder:
        raise EvaluationError(f"integration config contains an unresolved placeholder at {placeholder}")
    fixture_id = str(config.get("fixture_id") or "").strip()
    if not fixture_id:
        raise EvaluationError("integration config requires fixture_id")
    if not str(config.get("postgres_fixture_review_id") or "").strip():
        raise EvaluationError("integration config requires postgres_fixture_review_id")
    snapshots = config.get("snapshots")
    if not isinstance(snapshots, Mapping):
        raise EvaluationError("integration config requires snapshots")
    missing_snapshots = [
        store
        for store in ("neo4j", "postgres", "qdrant")
        if not str(snapshots.get(store) or "").strip()
    ]
    if missing_snapshots:
        raise EvaluationError(
            f"integration config requires snapshot IDs for: {', '.join(missing_snapshots)}"
        )
    checks = config.get("checks")
    if not isinstance(checks, Mapping):
        raise EvaluationError("integration config requires a checks object")
    missing = sorted(set(EXPECTED_ACCEPTANCE_IDS) - set(checks))
    unexpected = sorted(set(checks) - set(EXPECTED_ACCEPTANCE_IDS))
    if missing or unexpected:
        raise EvaluationError(
            f"integration checks mismatch; missing={missing}, unexpected={unexpected}"
        )
    for check_id in EXPECTED_ACCEPTANCE_IDS:
        spec = checks[check_id]
        if not isinstance(spec, Mapping):
            raise EvaluationError(f"integration check {check_id} must be an object")
        assertion = spec.get("assertion")
        if not isinstance(assertion, Mapping):
            raise EvaluationError(f"integration check {check_id} requires an assertion")
        assertion_type = str(assertion.get("type") or "")
        if check_id in _NEGATIVE_NEO4J_CHECKS and assertion_type != "empty":
            raise EvaluationError(f"integration check {check_id} must use an empty assertion")
        if check_id not in _NEGATIVE_NEO4J_CHECKS and assertion_type == "empty":
            raise EvaluationError(
                f"integration check {check_id} cannot use an empty assertion"
            )


def _row_data(row: Any) -> dict[str, Any]:
    if callable(getattr(row, "data", None)):
        return dict(row.data())
    return dict(row)


async def _async_rows(result: Any) -> list[dict[str, Any]]:
    if hasattr(result, "__aiter__"):
        return [_row_data(row) async for row in result]
    return [_row_data(row) for row in result]


async def run_neo4j_acceptance(
    driver: Any,
    catalog_path: Path,
    checks: Mapping[str, Any],
    *,
    database: str | None = None,
) -> dict[str, Any]:
    if not driver or not hasattr(driver, "session"):
        raise EvaluationError("neo4j driver is unavailable")
    catalog = load_acceptance_catalog(catalog_path)
    results: list[dict[str, Any]] = []
    session_kwargs: dict[str, Any] = {"default_access_mode": "READ"}
    if database:
        session_kwargs["database"] = database
    async with driver.session(**session_kwargs) as session:
        for check_id in EXPECTED_ACCEPTANCE_IDS:
            spec = checks[check_id]
            if not isinstance(spec, Mapping):
                raise EvaluationError(f"integration check {check_id} must be an object")
            assertion = spec.get("assertion") or {}
            query_result = await session.run(
                catalog[check_id].query,
                **dict(spec.get("params") or {}),
            )
            rows = await _async_rows(query_result)
            passed, message = assert_rows(rows, assertion)
            results.append(
                {
                    "check_id": check_id,
                    "title": catalog[check_id].title,
                    "passed": passed,
                    "row_count": len(rows),
                    "assertion": assertion,
                    "message": message,
                }
            )
    return {
        "mode": "read_only",
        "check_count": len(results),
        "results": results,
        "passed": all(row["passed"] for row in results),
    }


async def run_postgres_acceptance(pool: Any, fixture_review_id: str) -> dict[str, Any]:
    if not pool or not hasattr(pool, "acquire"):
        raise EvaluationError("postgres pool is unavailable")
    results: list[dict[str, Any]] = []
    async with pool.acquire() as connection:
        async with connection.transaction(readonly=True):
            for check in POSTGRES_ACCEPTANCE_CHECKS:
                args = (fixture_review_id,) if check.check_id == "PG07" else ()
                rows = [dict(row) for row in await connection.fetch(check.query, *args)]
                results.append(
                    {
                        "check_id": check.check_id,
                        "title": check.title,
                        "passed": not rows,
                        "violation_count": len(rows),
                        "violations": rows,
                    }
                )
    return {
        "mode": "read_only_transaction",
        "check_count": len(results),
        "results": results,
        "passed": all(row["passed"] for row in results),
    }


async def run_qdrant_parity(driver: Any, qdrant: Any) -> dict[str, Any]:
    if not qdrant or not hasattr(qdrant, "list_payload_records"):
        raise EvaluationError("qdrant payload reader is unavailable")
    neo4j_rows = await load_leaf_provisions_from_neo4j(driver)
    qdrant_rows = await qdrant.list_payload_records(
        LEGAL_PROVISION_COLLECTION,
        ["provision_id", "text_checksum"],
    )
    neo4j_ids = [str(row["provision_id"]) for row in neo4j_rows if row.get("provision_id")]
    qdrant_ids = [str(row["provision_id"]) for row in qdrant_rows if row.get("provision_id")]
    neo4j_checksums = {
        str(row["provision_id"]): str(row.get("text_checksum") or "")
        for row in neo4j_rows
        if row.get("provision_id")
    }
    qdrant_checksums = {
        str(row["provision_id"]): str(row.get("text_checksum") or "")
        for row in qdrant_rows
        if row.get("provision_id")
    }
    report = build_shadow_parity_report(
        neo4j_ids,
        qdrant_ids,
        neo4j_checksums=neo4j_checksums,
        qdrant_checksums=qdrant_checksums,
    )
    return {
        "mode": "read_only",
        "collection": LEGAL_PROVISION_COLLECTION,
        **report,
        "passed": bool(report["exact_match"]),
    }


async def run_integration_acceptance(
    *,
    driver: Any,
    postgres_pool: Any,
    qdrant: Any,
    catalog_path: Path,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    validate_integration_config(config)
    async def capture(store: str, operation: Any) -> dict[str, Any]:
        try:
            return await operation
        except Exception as exc:  # noqa: BLE001 - retain per-store failure evidence
            return {
                "mode": "read_only",
                "passed": False,
                "error": f"{type(exc).__name__}: {exc}",
                "store": store,
            }

    neo4j = await capture(
        "neo4j",
        run_neo4j_acceptance(
            driver,
            catalog_path,
            config["checks"],
            database=str(config.get("database") or "").strip() or None,
        ),
    )
    postgres = await capture(
        "postgres",
        run_postgres_acceptance(
            postgres_pool,
            str(config["postgres_fixture_review_id"]),
        ),
    )
    qdrant_parity = await capture("qdrant", run_qdrant_parity(driver, qdrant))
    stores = {
        "neo4j": neo4j,
        "postgres": postgres,
        "qdrant_parity": qdrant_parity,
    }
    return {
        "schema_version": "1.0",
        "mode": "read_only_integration_acceptance",
        "fixture_id": config["fixture_id"],
        "snapshots": dict(config["snapshots"]),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "stores": stores,
        "passed": all(store["passed"] for store in stores.values()),
        "mutated": False,
    }


__all__ = [
    "POSTGRES_ACCEPTANCE_CHECKS",
    "run_integration_acceptance",
    "run_neo4j_acceptance",
    "run_postgres_acceptance",
    "run_qdrant_parity",
    "validate_integration_config",
]
