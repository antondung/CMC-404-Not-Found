from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Sequence


def percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return round(ordered[index], 6)


def build_shadow_report(
    cases: list[dict[str, Any]],
    *,
    fixture_id: str,
    minimum_cases: int = 100,
    maximum_p95_regression_ratio: float = 1.2,
) -> dict[str, Any]:
    successful = [case for case in cases if case.get("success") is True]
    candidate_latencies = [float(case["latency_ms"]) for case in successful]
    baseline_latencies = [float(case["baseline_latency_ms"]) for case in successful]
    p95 = percentile(candidate_latencies, 0.95)
    baseline_p95 = percentile(baseline_latencies, 0.95)
    regression = p95 / baseline_p95 if baseline_p95 else float("inf")
    failures = len(cases) - len(successful)
    parity_matches = sum(case.get("parity_match") is True for case in cases)
    metrics = {
        "case_count": len(cases),
        "success_count": len(successful),
        "failure_count": failures,
        "failure_rate": failures / len(cases) if cases else 1.0,
        "parity_rate": parity_matches / len(cases) if cases else 0.0,
        "candidate_p50_ms": percentile(candidate_latencies, 0.50),
        "candidate_p95_ms": p95,
        "baseline_p50_ms": percentile(baseline_latencies, 0.50),
        "baseline_p95_ms": baseline_p95,
        "p95_regression_ratio": round(regression, 6),
        "estimated_cost_usd": round(
            sum(float(case.get("estimated_cost_usd") or 0.0) for case in cases),
            8,
        ),
        "llm_calls": sum(int(case.get("llm_calls") or 0) for case in cases),
    }
    gates = [
        {
            "gate": "minimum_case_count",
            "actual": len(cases),
            "target": minimum_cases,
            "passed": len(cases) >= minimum_cases,
        },
        {
            "gate": "failure_rate",
            "actual": metrics["failure_rate"],
            "target": 0.0,
            "passed": metrics["failure_rate"] == 0.0,
        },
        {
            "gate": "temporal_leaf_parity",
            "actual": metrics["parity_rate"],
            "target": 1.0,
            "passed": metrics["parity_rate"] == 1.0,
        },
        {
            "gate": "p95_regression_ratio",
            "actual": metrics["p95_regression_ratio"],
            "target": maximum_p95_regression_ratio,
            "passed": metrics["p95_regression_ratio"] <= maximum_p95_regression_ratio,
        },
    ]
    return {
        "schema_version": "1.0",
        "evidence_kind": "measured_local_shadow_read",
        "fixture_id": fixture_id,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "gates": gates,
        "passed": all(gate["passed"] for gate in gates),
        "release_eligible": False,
        "limitations": [
            "Measurements use the localhost synthetic integration fixture.",
            "No LLM or paid external API is invoked; estimated cost is zero.",
            "Local measurements cannot replace production-like shadow evidence or independent legal holdouts.",
        ],
        "cases": cases,
    }


def system_evaluation_payloads(report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata = {
        "dataset_id": f"{report['fixture_id']}-shadow-system-v1",
        "dataset_kind": "measured_local_shadow_read",
        "independent_review": False,
        "measured_at": report["measured_at"],
    }
    gold = {
        "metadata": metadata,
        "cases": [
            {"case_id": str(case["case_id"]), "expected_success": True}
            for case in report["cases"]
        ],
    }
    predictions = {
        "predictions": [
            {
                "case_id": str(case["case_id"]),
                "success": bool(case.get("success")),
                "latency_ms": float(case.get("latency_ms") or 0.0),
                "baseline_latency_ms": float(case.get("baseline_latency_ms") or 0.0),
            }
            for case in report["cases"]
        ]
    }
    return gold, predictions


__all__ = ["build_shadow_report", "percentile", "system_evaluation_payloads"]
