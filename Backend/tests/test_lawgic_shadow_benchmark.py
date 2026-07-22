from __future__ import annotations

from app.evaluation.shadow_benchmark import (
    build_shadow_report,
    percentile,
    system_evaluation_payloads,
)


def _cases(count: int = 100) -> list[dict[str, object]]:
    return [
        {
            "case_id": f"case-{index}",
            "success": True,
            "parity_match": True,
            "latency_ms": 11.0,
            "baseline_latency_ms": 10.0,
            "estimated_cost_usd": 0.0,
            "llm_calls": 0,
        }
        for index in range(count)
    ]


def test_percentile_uses_nearest_rank() -> None:
    assert percentile([1, 2, 3, 4], 0.50) == 2.0
    assert percentile([1, 2, 3, 4], 0.95) == 4.0


def test_shadow_report_passes_complete_measured_workload() -> None:
    report = build_shadow_report(_cases(), fixture_id="fixture-v1")

    assert report["passed"] is True
    assert report["release_eligible"] is False
    assert report["metrics"]["case_count"] == 100
    assert report["metrics"]["failure_rate"] == 0.0
    assert report["metrics"]["parity_rate"] == 1.0
    assert report["metrics"]["p95_regression_ratio"] == 1.1
    assert report["metrics"]["estimated_cost_usd"] == 0.0


def test_shadow_report_fails_on_parity_or_minimum_sample_regression() -> None:
    cases = _cases(99)
    cases[0]["success"] = False
    cases[0]["parity_match"] = False

    report = build_shadow_report(cases, fixture_id="fixture-v1")

    assert report["passed"] is False
    failed = {gate["gate"] for gate in report["gates"] if not gate["passed"]}
    assert failed == {"minimum_case_count", "failure_rate", "temporal_leaf_parity"}


def test_shadow_report_fails_when_p95_regresses_over_twenty_percent() -> None:
    cases = _cases()
    for case in cases:
        case["latency_ms"] = 13.0

    report = build_shadow_report(cases, fixture_id="fixture-v1")

    assert report["passed"] is False
    gate = next(item for item in report["gates"] if item["gate"] == "p95_regression_ratio")
    assert gate["actual"] == 1.3
    assert gate["passed"] is False


def test_shadow_cases_export_to_system_evaluation_contract() -> None:
    report = build_shadow_report(_cases(), fixture_id="fixture-v1")

    gold, predictions = system_evaluation_payloads(report)

    assert gold["metadata"]["dataset_kind"] == "measured_local_shadow_read"
    assert len(gold["cases"]) == 100
    assert len(predictions["predictions"]) == 100
    assert predictions["predictions"][0]["success"] is True
