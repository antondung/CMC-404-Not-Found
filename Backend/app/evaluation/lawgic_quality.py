from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


class EvaluationError(ValueError):
    """Raised when evaluation evidence does not satisfy the data contract."""


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _release_review_issues(metadata: Mapping[str, Any]) -> list[str]:
    """Return missing/invalid provenance required for release evidence."""

    issues: list[str] = []
    if metadata.get("independent_review") is not True:
        issues.append("independent_review_must_be_true")

    reviewer_ids = metadata.get("reviewer_ids")
    reviewers = (
        [str(value).strip() for value in reviewer_ids]
        if isinstance(reviewer_ids, list)
        else []
    )
    if len(reviewers) < 2 or len(set(reviewers)) != len(reviewers) or any(not value for value in reviewers):
        issues.append("at_least_two_distinct_reviewer_ids_required")

    if str(metadata.get("adjudication_status") or "").strip() != "adjudicated":
        issues.append("adjudication_status_must_be_adjudicated")
    if not str(metadata.get("guideline_version") or "").strip():
        issues.append("guideline_version_required")

    checksum = str(metadata.get("source_dataset_sha256") or "").strip().lower()
    if not _SHA256_PATTERN.fullmatch(checksum):
        issues.append("valid_source_dataset_sha256_required")
    return issues


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _load_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise EvaluationError(f"missing evaluation file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvaluationError(f"evaluation file must contain an object: {path}")
    return value


def _case_map(payload: Mapping[str, Any], path: Path) -> dict[str, dict[str, Any]]:
    rows = payload.get("cases")
    if not isinstance(rows, list) or not rows:
        raise EvaluationError(f"{path} must contain a non-empty cases list")
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise EvaluationError(f"{path} case {index} must be an object")
        case_id = str(row.get("case_id") or "").strip()
        if not case_id:
            raise EvaluationError(f"{path} case {index} is missing case_id")
        if case_id in result:
            raise EvaluationError(f"duplicate case_id {case_id!r} in {path}")
        result[case_id] = row
    return result


def _prediction_map(payload: Mapping[str, Any], path: Path) -> dict[str, dict[str, Any]]:
    rows = payload.get("predictions")
    if not isinstance(rows, list):
        raise EvaluationError(f"{path} must contain a predictions list")
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise EvaluationError(f"{path} prediction {index} must be an object")
        case_id = str(row.get("case_id") or "").strip()
        if not case_id:
            raise EvaluationError(f"{path} prediction {index} is missing case_id")
        if case_id in result:
            raise EvaluationError(f"duplicate prediction for {case_id!r} in {path}")
        result[case_id] = row
    return result


def _classification(expected: list[str], predicted: list[str]) -> dict[str, Any]:
    labels = sorted(set(expected) | set(predicted))
    per_label: dict[str, dict[str, float | int]] = {}
    for label in labels:
        true_positive = sum(e == label and p == label for e, p in zip(expected, predicted))
        false_positive = sum(e != label and p == label for e, p in zip(expected, predicted))
        false_negative = sum(e == label and p != label for e, p in zip(expected, predicted))
        precision = _ratio(true_positive, true_positive + false_positive)
        recall = _ratio(true_positive, true_positive + false_negative)
        f1 = _ratio(2 * precision * recall, precision + recall)
        per_label[label] = {
            "support": sum(e == label for e in expected),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return {
        "accuracy": _ratio(sum(e == p for e, p in zip(expected, predicted)), len(expected)),
        "macro_f1": _ratio(sum(float(row["f1"]) for row in per_label.values()), len(per_label)),
        "per_label": per_label,
    }


def _evaluate_parser(
    gold: Mapping[str, dict[str, Any]], predictions: Mapping[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, float]]:
    expected_counts = defaultdict(int)
    matched_counts = defaultdict(int)
    expected_characters = 0
    preserved_characters = 0
    invariant_errors = 0
    for case_id, expected in gold.items():
        predicted = predictions.get(case_id, {})
        expected_by_level = expected.get("expected_ids_by_level") or {}
        predicted_by_level = predicted.get("predicted_ids_by_level") or {}
        for level in ("dieu", "khoan", "diem"):
            expected_ids = set(expected_by_level.get(level) or [])
            predicted_ids = set(predicted_by_level.get(level) or [])
            expected_counts[level] += len(expected_ids)
            matched_counts[level] += len(expected_ids & predicted_ids)
        expected_characters += max(0, int(expected.get("expected_character_count") or 0))
        preserved_characters += max(0, int(predicted.get("preserved_character_count") or 0))
        invariant_errors += max(0, int(predicted.get("invariant_errors") or 0))
    recalls = {
        level: _ratio(matched_counts[level], expected_counts[level])
        for level in ("dieu", "khoan", "diem")
    }
    character_coverage = min(1.0, _ratio(preserved_characters, expected_characters))
    details = {
        "case_count": len(gold),
        "recall_by_level": recalls,
        "character_coverage": character_coverage,
        "invariant_errors": invariant_errors,
    }
    flat = {f"parser.recall_{level}": value for level, value in recalls.items()}
    flat.update(
        {
            "parser.character_coverage": character_coverage,
            "parser.invariant_errors": float(invariant_errors),
        }
    )
    return details, flat


def _evaluate_retrieval(
    gold: Mapping[str, dict[str, Any]], predictions: Mapping[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, float]]:
    profile_names = sorted(
        {
            str(profile)
            for row in predictions.values()
            for profile in (row.get("profiles") or {}).keys()
        }
    )
    if not profile_names:
        raise EvaluationError("retrieval predictions require at least one profile")
    details: dict[str, Any] = {"case_count": len(gold), "profiles": {}}
    flat: dict[str, float] = {}
    for profile in profile_names:
        recall_at_1: list[float] = []
        recall_at_5: list[float] = []
        reciprocal_ranks: list[float] = []
        ndcg_at_5: list[float] = []
        for case_id, expected in gold.items():
            relevant = list(dict.fromkeys(expected.get("expected_ids") or []))
            ranked = list(dict.fromkeys((predictions.get(case_id, {}).get("profiles") or {}).get(profile) or []))
            relevant_set = set(relevant)
            recall_at_1.append(_ratio(len(relevant_set & set(ranked[:1])), len(relevant_set)))
            recall_at_5.append(_ratio(len(relevant_set & set(ranked[:5])), len(relevant_set)))
            first_rank = next((index for index, item in enumerate(ranked, start=1) if item in relevant_set), None)
            reciprocal_ranks.append(1.0 / first_rank if first_rank else 0.0)
            dcg = sum(1.0 / math.log2(index + 1) for index, item in enumerate(ranked[:5], start=1) if item in relevant_set)
            ideal = sum(1.0 / math.log2(index + 1) for index in range(1, min(5, len(relevant_set)) + 1))
            ndcg_at_5.append(_ratio(dcg, ideal))
        metrics = {
            "recall_at_1": _ratio(sum(recall_at_1), len(recall_at_1)),
            "recall_at_5": _ratio(sum(recall_at_5), len(recall_at_5)),
            "mrr": _ratio(sum(reciprocal_ranks), len(reciprocal_ranks)),
            "ndcg_at_5": _ratio(sum(ndcg_at_5), len(ndcg_at_5)),
        }
        details["profiles"][profile] = metrics
        flat.update({f"retrieval.{profile}.{key}": value for key, value in metrics.items()})
    vector = details["profiles"].get("vector", {}).get("recall_at_5")
    full = details["profiles"].get("hybrid_graph_rerank", {}).get("recall_at_5")
    if vector is not None and full is not None:
        delta = float(full) - float(vector)
        details["ablation_delta_recall_at_5"] = delta
        flat["retrieval.ablation_delta_recall_at_5"] = delta
    return details, flat


def _evaluate_temporal(
    gold: Mapping[str, dict[str, Any]], predictions: Mapping[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, float]]:
    exact = 0
    for case_id, expected in gold.items():
        expected_ids = set(expected.get("expected_active_ids") or [])
        predicted_ids = set(predictions.get(case_id, {}).get("predicted_active_ids") or [])
        exact += expected_ids == predicted_ids
    accuracy = _ratio(exact, len(gold))
    return {"case_count": len(gold), "exact_active_node_accuracy": accuracy}, {
        "temporal.exact_active_node_accuracy": accuracy
    }


def _evaluate_citation(
    gold: Mapping[str, dict[str, Any]], predictions: Mapping[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, float]]:
    exact_nodes = 0
    strict_valid = 0
    support_expected: list[str] = []
    support_predicted: list[str] = []
    for case_id, expected in gold.items():
        predicted = predictions.get(case_id, {})
        node_matches = predicted.get("node_id") == expected.get("expected_node_id")
        exact_nodes += node_matches
        quote_matches = bool(predicted.get("quote_exact")) == bool(expected.get("expected_quote_exact", True))
        effective_matches = bool(predicted.get("effective")) == bool(expected.get("expected_effective", True))
        exists_matches = bool(predicted.get("node_exists")) == bool(expected.get("expected_node_exists", True))
        strict_valid += node_matches and quote_matches and effective_matches and exists_matches
        support_expected.append("supported" if expected.get("expected_support", True) else "unsupported")
        support_predicted.append("supported" if predicted.get("supports_claim") else "unsupported")
    support = _classification(support_expected, support_predicted)
    exact_accuracy = _ratio(exact_nodes, len(gold))
    validity_rate = _ratio(strict_valid, len(gold))
    details = {
        "case_count": len(gold),
        "exact_node_accuracy": exact_accuracy,
        "canonical_validity_rate": validity_rate,
        "support_classification": support,
    }
    return details, {
        "citation.exact_node_accuracy": exact_accuracy,
        "citation.canonical_validity_rate": validity_rate,
        "citation.support_macro_f1": float(support["macro_f1"]),
    }


def _pair(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, dict):
        return None
    old_id = str(value.get("old_id") or "").strip()
    new_id = str(value.get("new_id") or "").strip()
    return (old_id, new_id) if old_id and new_id else None


def _evaluate_amendment(
    gold: Mapping[str, dict[str, Any]], predictions: Mapping[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, float]]:
    expected_pairs = 0
    predicted_pairs = 0
    correct_pairs = 0
    expected_types: list[str] = []
    predicted_types: list[str] = []
    auto_approved = 0
    correct_auto_approved = 0
    for case_id, expected in gold.items():
        predicted = predictions.get(case_id, {})
        expected_pair = _pair(expected.get("expected_pair"))
        predicted_pair = _pair(predicted.get("predicted_pair"))
        expected_pairs += expected_pair is not None
        predicted_pairs += predicted_pair is not None
        correct_pairs += expected_pair is not None and predicted_pair == expected_pair
        expected_types.append(str(expected.get("expected_change_type") or "MISSING"))
        predicted_types.append(str(predicted.get("predicted_change_type") or "MISSING"))
        if predicted.get("auto_approved"):
            auto_approved += 1
            correct_auto_approved += (
                bool(expected.get("auto_approve_allowed"))
                and expected_pair is not None
                and predicted_pair == expected_pair
            )
    pairing_precision = _ratio(correct_pairs, predicted_pairs)
    pairing_recall = _ratio(correct_pairs, expected_pairs)
    auto_precision = _ratio(correct_auto_approved, auto_approved)
    change = _classification(expected_types, predicted_types)
    details = {
        "case_count": len(gold),
        "pairing_precision": pairing_precision,
        "pairing_recall": pairing_recall,
        "change_type": change,
        "review_rate": _ratio(len(gold) - auto_approved, len(gold)),
        "auto_approved_pairing_precision": auto_precision,
        "auto_approved_count": auto_approved,
    }
    return details, {
        "amendment.pairing_precision": pairing_precision,
        "amendment.pairing_recall": pairing_recall,
        "amendment.change_type_macro_f1": float(change["macro_f1"]),
        "amendment.auto_approved_pairing_precision": auto_precision,
    }


def _cluster_pairwise(
    case_ids: list[str], expected_clusters: Mapping[str, str], predicted_clusters: Mapping[str, str]
) -> dict[str, float]:
    true_positive = false_positive = false_negative = 0
    for left_index, left_id in enumerate(case_ids):
        for right_id in case_ids[left_index + 1 :]:
            expected_same = expected_clusters[left_id] == expected_clusters[right_id]
            predicted_same = predicted_clusters.get(left_id, "") == predicted_clusters.get(right_id, "")
            true_positive += expected_same and predicted_same
            false_positive += not expected_same and predicted_same
            false_negative += expected_same and not predicted_same
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    return {
        "precision": precision,
        "recall": recall,
        "f1": _ratio(2 * precision * recall, precision + recall),
    }


def _evaluate_misinformation(
    gold: Mapping[str, dict[str, Any]], predictions: Mapping[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, float]]:
    expected_verdicts: list[str] = []
    predicted_verdicts: list[str] = []
    expected_clusters: dict[str, str] = {}
    predicted_clusters: dict[str, str] = {}
    predicted_high_risk = 0
    correct_high_risk = 0
    for case_id, expected in gold.items():
        predicted = predictions.get(case_id, {})
        expected_verdicts.append(str(expected.get("expected_verdict") or "MISSING"))
        predicted_verdicts.append(str(predicted.get("predicted_verdict") or "MISSING"))
        expected_clusters[case_id] = str(expected.get("expected_cluster_id") or case_id)
        predicted_clusters[case_id] = str(predicted.get("predicted_cluster_id") or f"missing:{case_id}")
        if predicted.get("predicted_high_risk"):
            predicted_high_risk += 1
            correct_high_risk += bool(expected.get("expected_high_risk"))
    verdict = _classification(expected_verdicts, predicted_verdicts)
    clusters = _cluster_pairwise(list(gold), expected_clusters, predicted_clusters)
    outdated = verdict["per_label"].get("OUTDATED_BUT_PREVIOUSLY_TRUE", {"f1": 0.0})
    risk_precision = _ratio(correct_high_risk, predicted_high_risk)
    details = {
        "case_count": len(gold),
        "verdict": verdict,
        "cluster_pairwise": clusters,
        "outdated_verdict_f1": float(outdated["f1"]),
        "high_risk_precision": risk_precision,
    }
    return details, {
        "misinformation.verdict_macro_f1": float(verdict["macro_f1"]),
        "misinformation.outdated_verdict_f1": float(outdated["f1"]),
        "misinformation.cluster_pairwise_f1": clusters["f1"],
        "misinformation.high_risk_precision": risk_precision,
    }


def _evaluate_safety(
    gold: Mapping[str, dict[str, Any]], predictions: Mapping[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, float]]:
    required = refused_required = allowed = over_refused = correct = 0
    for case_id, expected in gold.items():
        should_refuse = bool(expected.get("expected_refused"))
        refused = bool(predictions.get(case_id, {}).get("refused"))
        correct += should_refuse == refused
        if should_refuse:
            required += 1
            refused_required += refused
        else:
            allowed += 1
            over_refused += refused
    required_rate = _ratio(refused_required, required)
    over_refusal = _ratio(over_refused, allowed)
    accuracy = _ratio(correct, len(gold))
    return {
        "case_count": len(gold),
        "required_refusal_rate": required_rate,
        "over_refusal_rate": over_refusal,
        "accuracy": accuracy,
    }, {
        "safety.required_refusal_rate": required_rate,
        "safety.over_refusal_rate": over_refusal,
        "safety.accuracy": accuracy,
    }


def _evaluate_system(
    gold: Mapping[str, dict[str, Any]], predictions: Mapping[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, float]]:
    latencies: list[float] = []
    baselines: list[float] = []
    failures = 0
    for case_id in gold:
        predicted = predictions.get(case_id, {})
        success = bool(predicted.get("success"))
        failures += not success
        if success:
            latencies.append(max(0.0, float(predicted.get("latency_ms") or 0.0)))
        baselines.append(max(0.0, float(predicted.get("baseline_latency_ms") or 0.0)))
    p50 = _percentile(latencies, 0.50)
    p95 = _percentile(latencies, 0.95)
    baseline_p95 = _percentile(baselines, 0.95)
    regression = _ratio(p95, baseline_p95)
    failure_rate = _ratio(failures, len(gold))
    return {
        "case_count": len(gold),
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "baseline_p95_latency_ms": baseline_p95,
        "p95_regression_ratio": regression,
        "failure_rate": failure_rate,
    }, {
        "system.p95_latency_ms": p95,
        "system.p95_regression_ratio": regression,
        "system.failure_rate": failure_rate,
    }


_EVALUATORS: dict[
    str,
    Callable[
        [Mapping[str, dict[str, Any]], Mapping[str, dict[str, Any]]],
        tuple[dict[str, Any], dict[str, float]],
    ],
] = {
    "parser_structure": _evaluate_parser,
    "ranked_retrieval": _evaluate_retrieval,
    "temporal_exact": _evaluate_temporal,
    "citation_contract": _evaluate_citation,
    "amendment": _evaluate_amendment,
    "misinformation": _evaluate_misinformation,
    "safety": _evaluate_safety,
    "system": _evaluate_system,
}


def _evaluate_constraints(
    constraints: Sequence[Mapping[str, Any]], metric_values: Mapping[str, float]
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    operators: dict[str, Callable[[float, float], bool]] = {
        "min": lambda actual, target: actual >= target,
        "max": lambda actual, target: actual <= target,
        "eq": lambda actual, target: actual == target,
    }
    for constraint in constraints:
        metric = str(constraint.get("metric") or "")
        operator = str(constraint.get("operator") or "")
        if operator not in operators:
            raise EvaluationError(f"unsupported gate operator: {operator!r}")
        target = float(constraint.get("value"))
        actual = metric_values.get(metric)
        passed = actual is not None and operators[operator](float(actual), target)
        results.append(
            {
                "metric": metric,
                "operator": operator,
                "target": target,
                "actual": actual,
                "passed": passed,
                "severity": str(constraint.get("severity") or "blocking"),
            }
        )
    return results


def evaluate_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = _load_object(manifest_path)
    base = manifest_path.parent
    suite_specs = manifest.get("suites")
    if not isinstance(suite_specs, list) or not suite_specs:
        raise EvaluationError("manifest requires a non-empty suites list")
    gates_path = (base / str(manifest.get("gates") or "")).resolve()
    gates = _load_object(gates_path)
    suite_reports: dict[str, Any] = {}
    metric_values: dict[str, float] = {}
    evidence: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    minimum_cases = gates.get("minimum_release_cases") or {}

    for spec in suite_specs:
        if not isinstance(spec, dict):
            raise EvaluationError("every suite specification must be an object")
        name = str(spec.get("name") or "").strip()
        task = str(spec.get("task") or "").strip()
        if not name or name in seen_names:
            raise EvaluationError(f"invalid or duplicate suite name: {name!r}")
        if task not in _EVALUATORS:
            raise EvaluationError(f"unsupported evaluation task: {task!r}")
        seen_names.add(name)
        gold_path = (base / str(spec.get("gold") or "")).resolve()
        predictions_path = (base / str(spec.get("predictions") or "")).resolve()
        gold_payload = _load_object(gold_path)
        prediction_payload = _load_object(predictions_path)
        gold_rows = _case_map(gold_payload, gold_path)
        prediction_rows = _prediction_map(prediction_payload, predictions_path)
        details, flat = _EVALUATORS[task](gold_rows, prediction_rows)
        unknown_predictions = sorted(set(prediction_rows) - set(gold_rows))
        missing_predictions = sorted(set(gold_rows) - set(prediction_rows))
        metadata = gold_payload.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise EvaluationError(f"metadata must be an object: {gold_path}")
        kind = str(metadata.get("dataset_kind") or "unspecified")
        independent = metadata.get("independent_review") is True
        minimum = max(1, int(minimum_cases.get(name) or 1))
        review_issues = _release_review_issues(metadata) if kind == "independent_holdout" else []
        release_eligible = (
            kind == "independent_holdout"
            and not review_issues
            and len(gold_rows) >= minimum
        )
        evidence.append(
            {
                "suite": name,
                "dataset_id": metadata.get("dataset_id"),
                "dataset_kind": kind,
                "independent_review": independent,
                "case_count": len(gold_rows),
                "minimum_release_cases": minimum,
                "review_provenance_issues": review_issues,
                "release_eligible": release_eligible,
            }
        )
        suite_reports[name] = {
            "task": task,
            "metrics": details,
            "missing_prediction_ids": missing_predictions,
            "unknown_prediction_ids": unknown_predictions,
        }
        metric_values.update(flat)

    gate_results = _evaluate_constraints(gates.get("constraints") or [], metric_values)
    blocking_passed = all(
        row["passed"] for row in gate_results if row.get("severity") == "blocking"
    )
    evidence_eligible = all(item["release_eligible"] for item in evidence)
    return {
        "schema_version": "1.0",
        "manifest_id": manifest.get("manifest_id"),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "suites": suite_reports,
        "metric_values": dict(sorted(metric_values.items())),
        "gates": gate_results,
        "blocking_gates_passed": blocking_passed,
        "evidence": evidence,
        "release_evidence_eligible": evidence_eligible,
        "release_decision": "GO" if blocking_passed and evidence_eligible else "NO_GO",
        "limitations": list(manifest.get("limitations") or []),
    }


__all__ = ["EvaluationError", "evaluate_manifest"]
