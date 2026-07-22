from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evaluation.acceptance_catalog import (
    EXPECTED_ACCEPTANCE_IDS,
    assert_rows,
    validate_acceptance_catalog,
)
from app.evaluation.lawgic_quality import EvaluationError, evaluate_manifest


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_smoke_manifest_passes_contract_gates_but_is_not_release_evidence() -> None:
    report = evaluate_manifest(ROOT / "eval" / "manifest.smoke.json")

    assert report["blocking_gates_passed"] is True
    assert report["release_evidence_eligible"] is False
    assert report["release_decision"] == "NO_GO"
    assert report["metric_values"]["temporal.exact_active_node_accuracy"] == 1.0
    assert report["metric_values"]["safety.required_refusal_rate"] == 1.0
    assert all(item["dataset_kind"] == "synthetic_contract_fixture" for item in report["evidence"])


def test_release_evidence_still_fails_when_a_blocking_metric_regresses(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "gold.json",
        {
            "metadata": {
                "dataset_id": "independent-safety",
                "dataset_kind": "independent_holdout",
                "independent_review": True,
                "reviewer_ids": ["reviewer-a", "reviewer-b"],
                "adjudication_status": "adjudicated",
                "guideline_version": "lawgic-holdout-v1",
                "source_dataset_sha256": "a" * 64,
            },
            "cases": [{"case_id": "no-basis", "expected_refused": True}],
        },
    )
    _write_json(
        tmp_path / "predictions.json",
        {"predictions": [{"case_id": "no-basis", "refused": False}]},
    )
    _write_json(
        tmp_path / "gates.json",
        {
            "minimum_release_cases": {"safety": 1},
            "constraints": [
                {
                    "metric": "safety.required_refusal_rate",
                    "operator": "eq",
                    "value": 1,
                    "severity": "blocking",
                }
            ],
        },
    )
    _write_json(
        tmp_path / "manifest.json",
        {
            "manifest_id": "release-regression",
            "gates": "gates.json",
            "suites": [
                {
                    "name": "safety",
                    "task": "safety",
                    "gold": "gold.json",
                    "predictions": "predictions.json",
                }
            ],
        },
    )

    report = evaluate_manifest(tmp_path / "manifest.json")

    assert report["release_evidence_eligible"] is True
    assert report["blocking_gates_passed"] is False
    assert report["release_decision"] == "NO_GO"


@pytest.mark.parametrize(
    ("metadata_patch", "expected_issue"),
    [
        ({"reviewer_ids": ["reviewer-a"]}, "at_least_two_distinct_reviewer_ids_required"),
        ({"adjudication_status": "pending"}, "adjudication_status_must_be_adjudicated"),
        ({"guideline_version": ""}, "guideline_version_required"),
        ({"source_dataset_sha256": "not-a-checksum"}, "valid_source_dataset_sha256_required"),
    ],
)
def test_release_holdout_requires_complete_review_provenance(
    tmp_path: Path,
    metadata_patch: dict[str, object],
    expected_issue: str,
) -> None:
    metadata: dict[str, object] = {
        "dataset_id": "independent-safety",
        "dataset_kind": "independent_holdout",
        "independent_review": True,
        "reviewer_ids": ["reviewer-a", "reviewer-b"],
        "adjudication_status": "adjudicated",
        "guideline_version": "lawgic-holdout-v1",
        "source_dataset_sha256": "b" * 64,
    }
    metadata.update(metadata_patch)
    _write_json(
        tmp_path / "gold.json",
        {"metadata": metadata, "cases": [{"case_id": "safe-1", "expected_refused": True}]},
    )
    _write_json(
        tmp_path / "predictions.json",
        {"predictions": [{"case_id": "safe-1", "refused": True}]},
    )
    _write_json(
        tmp_path / "gates.json",
        {"minimum_release_cases": {"safety": 1}, "constraints": []},
    )
    _write_json(
        tmp_path / "manifest.json",
        {
            "gates": "gates.json",
            "suites": [
                {
                    "name": "safety",
                    "task": "safety",
                    "gold": "gold.json",
                    "predictions": "predictions.json",
                }
            ],
        },
    )

    report = evaluate_manifest(tmp_path / "manifest.json")

    assert report["blocking_gates_passed"] is True
    assert report["release_evidence_eligible"] is False
    assert report["release_decision"] == "NO_GO"
    assert expected_issue in report["evidence"][0]["review_provenance_issues"]


def test_duplicate_gold_case_ids_are_rejected(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "gold.json",
        {
            "metadata": {},
            "cases": [
                {"case_id": "duplicate", "expected_refused": True},
                {"case_id": "duplicate", "expected_refused": True},
            ],
        },
    )
    _write_json(tmp_path / "predictions.json", {"predictions": []})
    _write_json(tmp_path / "gates.json", {"constraints": []})
    _write_json(
        tmp_path / "manifest.json",
        {
            "gates": "gates.json",
            "suites": [
                {
                    "name": "safety",
                    "task": "safety",
                    "gold": "gold.json",
                    "predictions": "predictions.json",
                }
            ],
        },
    )

    with pytest.raises(EvaluationError, match="duplicate case_id"):
        evaluate_manifest(tmp_path / "manifest.json")


def test_acceptance_catalog_contains_t01_t20_and_n01_n02() -> None:
    report = validate_acceptance_catalog(ROOT / "Data" / "schema" / "acceptance_queries.cypher")

    assert report["valid"] is True
    assert report["actual_count"] == 22
    assert report["check_ids"] == list(EXPECTED_ACCEPTANCE_IDS)


@pytest.mark.parametrize(
    ("rows", "assertion", "expected"),
    [
        ([], {"type": "empty"}, True),
        ([{"count": 2}], {"type": "field_equals", "field": "count", "value": 2}, True),
        ([{"text": "canonical"}], {"type": "field_nonempty", "field": "text"}, True),
        (
            [{"count": 2, "ids": ["a", "b"]}],
            {
                "type": "all",
                "assertions": [
                    {"type": "field_equals", "field": "count", "value": 2},
                    {"type": "field_set_equals", "field": "ids", "value": ["b", "a"]},
                ],
            },
            True,
        ),
        ([{"ids": ["a", "b"]}], {"type": "field_set_equals", "field": "ids", "value": ["b", "a"]}, True),
        ([{"id": "leak"}], {"type": "empty"}, False),
    ],
)
def test_acceptance_assertions_are_deterministic(
    rows: list[dict[str, object]], assertion: dict[str, object], expected: bool
) -> None:
    passed, _ = assert_rows(rows, assertion)
    assert passed is expected
