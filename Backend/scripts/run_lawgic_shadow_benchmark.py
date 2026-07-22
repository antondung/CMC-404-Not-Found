"""Measure local temporal LAWGIC shadow reads against a direct Neo4j reference."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path
from time import perf_counter_ns
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
load_dotenv(_BACKEND / ".env")

from app.adapters.neo4j_temporal import Neo4jTemporalRepository
from app.evaluation.integration_fixture import FIXTURE_ID, LOGICAL_VB_ID
from app.evaluation.shadow_benchmark import build_shadow_report, system_evaluation_payloads
from app.services.temporal_law_service import TemporalLawService


_BASELINE_QUERY = """
/* lawgic_shadow_reference */
MATCH (p:LegalProvision {logical_vb_id: $logical_vb_id})
WHERE date(p.effective_from) <= date($as_of)
  AND (p.effective_to IS NULL OR date($as_of) < date(p.effective_to))
  AND coalesce(p.visibility, 'public') = 'public'
  AND coalesce(p.review_status, 'approved') = 'approved'
  AND NOT EXISTS {
    MATCH (p)-[:CO_KHOAN|CO_DIEM]->(child:LegalProvision)
    WHERE date(child.effective_from) <= date($as_of)
      AND (child.effective_to IS NULL OR date($as_of) < date(child.effective_to))
      AND coalesce(child.visibility, 'public') = 'public'
      AND coalesce(child.review_status, 'approved') = 'approved'
  }
RETURN p.provision_id AS provision_id,
       p.lineage_id AS lineage_id,
       p.parent_lineage_id AS parent_lineage_id,
       p.level AS level,
       p.version_no AS version_no,
       p.source_vb_id AS source_vb_id,
       p.logical_vb_id AS logical_vb_id,
       coalesce(p.noi_dung, p.tieu_de, '') AS text,
       p.effective_from AS effective_from,
       p.effective_to AS effective_to,
       p.text_checksum AS text_checksum,
       p.source_checksum AS source_checksum,
       coalesce(p.visibility, 'public') AS visibility,
       p.recorded_at AS recorded_at,
       coalesce(p.review_status, 'approved') AS review_status
ORDER BY provision_id
"""


def _require_local_uri(value: str | None) -> str:
    raw = str(value or "").strip()
    host = (urlparse(raw).hostname or "").lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError(f"shadow benchmark requires localhost Neo4j, received {host!r}")
    return raw


async def _reference_read(driver: Any, as_of: date) -> list[str]:
    async with driver.session(default_access_mode="READ") as session:
        async def collect(transaction: Any) -> list[str]:
            result = await transaction.run(
                _BASELINE_QUERY,
                logical_vb_id=LOGICAL_VB_ID,
                as_of=as_of.isoformat(),
            )
            return [str(record["provision_id"]) async for record in result]

        return await session.execute_read(collect)


async def _candidate_read(service: TemporalLawService, as_of: date) -> list[str]:
    response = await service.law_as_of(
        as_of,
        logical_vb_id=LOGICAL_VB_ID,
        audience="citizen",
    )
    return sorted(str(item["provision_id"]) for item in response["items"])


async def _measure(operation: Any) -> tuple[float, Any]:
    started = perf_counter_ns()
    value = await operation
    return (perf_counter_ns() - started) / 1_000_000, value


async def _run(iterations: int, warmup: int) -> dict[str, Any]:
    from neo4j import AsyncGraphDatabase

    uri = _require_local_uri(os.getenv("NEO4J_URI") or os.getenv("NEO4J_URL"))
    driver = AsyncGraphDatabase.driver(
        uri,
        auth=(
            os.getenv("NEO4J_USER", "neo4j"),
            os.getenv("NEO4J_PASSWORD", "password"),
        ),
    )
    service = TemporalLawService(Neo4jTemporalRepository(driver))
    dates = (date(2026, 6, 30), date(2026, 7, 21), date(2027, 1, 2))
    cases: list[dict[str, Any]] = []
    try:
        await driver.verify_connectivity()
        for index in range(warmup):
            as_of = dates[index % len(dates)]
            await _reference_read(driver, as_of)
            await _candidate_read(service, as_of)
        for index in range(iterations):
            as_of = dates[index % len(dates)]
            case_id = f"shadow-{index + 1:04d}-{as_of.isoformat()}"
            try:
                if index % 2 == 0:
                    baseline_ms, reference_ids = await _measure(_reference_read(driver, as_of))
                    candidate_ms, candidate_ids = await _measure(_candidate_read(service, as_of))
                else:
                    candidate_ms, candidate_ids = await _measure(_candidate_read(service, as_of))
                    baseline_ms, reference_ids = await _measure(_reference_read(driver, as_of))
                parity = sorted(reference_ids) == sorted(candidate_ids)
                cases.append(
                    {
                        "case_id": case_id,
                        "as_of": as_of.isoformat(),
                        "success": parity,
                        "parity_match": parity,
                        "latency_ms": round(candidate_ms, 6),
                        "baseline_latency_ms": round(baseline_ms, 6),
                        "reference_ids": sorted(reference_ids),
                        "candidate_ids": sorted(candidate_ids),
                        "estimated_cost_usd": 0.0,
                        "llm_calls": 0,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - failures are benchmark evidence
                cases.append(
                    {
                        "case_id": case_id,
                        "as_of": as_of.isoformat(),
                        "success": False,
                        "parity_match": False,
                        "latency_ms": 0.0,
                        "baseline_latency_ms": 0.0,
                        "estimated_cost_usd": 0.0,
                        "llm_calls": 0,
                        "error": f"{type(exc).__name__}: {exc}",
                        "error_details": getattr(exc, "details", None),
                    }
                )
    finally:
        await driver.close()
    return build_shadow_report(cases, fixture_id=FIXTURE_ID)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Run measured localhost LAWGIC temporal shadow reads.")
    parser.add_argument("--iterations", type=int, default=120)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("eval/reports/lawgic-shadow-local.json"))
    parser.add_argument("--system-gold-output", type=Path, default=Path("eval/fixtures/runtime/system.gold.local.json"))
    parser.add_argument("--system-predictions-output", type=Path, default=Path("eval/fixtures/runtime/system.predictions.local.json"))
    args = parser.parse_args()
    if args.iterations < 100:
        print(json.dumps({"passed": False, "error": "iterations must be at least 100"}))
        return 2
    if args.warmup < 0:
        print(json.dumps({"passed": False, "error": "warmup cannot be negative"}))
        return 2
    try:
        report = asyncio.run(_run(args.iterations, args.warmup))
    except Exception as exc:  # noqa: BLE001
        report = {
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
            "details": getattr(exc, "details", None),
        }
    _write_json(args.output, report)
    if report.get("cases"):
        gold, predictions = system_evaluation_payloads(report)
        _write_json(args.system_gold_output, gold)
        _write_json(args.system_predictions_output, predictions)
    summary = {
        "passed": report.get("passed", False),
        "metrics": report.get("metrics"),
        "output": str(args.output),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
