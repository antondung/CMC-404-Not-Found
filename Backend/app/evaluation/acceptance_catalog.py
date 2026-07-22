from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.evaluation.lawgic_quality import EvaluationError


EXPECTED_ACCEPTANCE_IDS = tuple(
    [f"T{index:02d}" for index in range(1, 21)] + ["N01", "N02"]
)
_MARKER = re.compile(r"^//\s*((?:T|N)\d{2})\s*[—-]\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class AcceptanceQuery:
    check_id: str
    title: str
    query: str


def load_acceptance_catalog(path: Path) -> dict[str, AcceptanceQuery]:
    if not path.exists():
        raise EvaluationError(f"missing acceptance catalog: {path}")
    source = path.read_text(encoding="utf-8")
    markers = list(_MARKER.finditer(source))
    catalog: dict[str, AcceptanceQuery] = {}
    for index, marker in enumerate(markers):
        check_id = marker.group(1)
        if check_id in catalog:
            raise EvaluationError(f"duplicate acceptance query: {check_id}")
        end = markers[index + 1].start() if index + 1 < len(markers) else len(source)
        block = source[marker.end() : end]
        query = "\n".join(
            line for line in block.splitlines() if not line.lstrip().startswith("//")
        ).strip()
        if not query:
            raise EvaluationError(f"acceptance query {check_id} is empty")
        catalog[check_id] = AcceptanceQuery(check_id, marker.group(2).strip(), query)
    return catalog


def validate_acceptance_catalog(path: Path) -> dict[str, Any]:
    catalog = load_acceptance_catalog(path)
    missing = sorted(set(EXPECTED_ACCEPTANCE_IDS) - set(catalog))
    unexpected = sorted(set(catalog) - set(EXPECTED_ACCEPTANCE_IDS))
    ordered_ids = [item for item in EXPECTED_ACCEPTANCE_IDS if item in catalog]
    return {
        "catalog": str(path),
        "expected_count": len(EXPECTED_ACCEPTANCE_IDS),
        "actual_count": len(catalog),
        "check_ids": ordered_ids,
        "missing": missing,
        "unexpected": unexpected,
        "valid": not missing and not unexpected,
    }


def assert_rows(rows: Sequence[Mapping[str, Any]], assertion: Mapping[str, Any]) -> tuple[bool, str]:
    assertion_type = str(assertion.get("type") or "")
    if assertion_type == "all":
        nested = assertion.get("assertions")
        if not isinstance(nested, list) or not nested:
            raise EvaluationError("all assertion requires a non-empty assertions list")
        messages: list[str] = []
        for item in nested:
            if not isinstance(item, Mapping):
                raise EvaluationError("nested acceptance assertion must be an object")
            passed, message = assert_rows(rows, item)
            messages.append(message)
            if not passed:
                return False, "; ".join(messages)
        return True, "; ".join(messages)
    if assertion_type == "empty":
        return (not rows, f"expected zero rows, received {len(rows)}")
    if assertion_type == "nonempty":
        return (bool(rows), "expected at least one row")
    if assertion_type == "row_count":
        expected = int(assertion.get("value") or 0)
        return (len(rows) == expected, f"expected {expected} rows, received {len(rows)}")
    if assertion_type == "field_equals":
        field = str(assertion.get("field") or "")
        expected = assertion.get("value")
        actual = rows[0].get(field) if rows else None
        return (actual == expected, f"expected {field}={expected!r}, received {actual!r}")
    if assertion_type == "field_nonempty":
        field = str(assertion.get("field") or "")
        actual = rows[0].get(field) if rows else None
        return (
            actual not in (None, "", [], {}),
            f"expected non-empty {field}, received {actual!r}",
        )
    if assertion_type == "field_set_equals":
        field = str(assertion.get("field") or "")
        expected = set(assertion.get("value") or [])
        actual = set(rows[0].get(field) or []) if rows else set()
        return (actual == expected, f"expected {field}={sorted(expected)!r}, received {sorted(actual)!r}")
    raise EvaluationError(f"unsupported acceptance assertion: {assertion_type!r}")


__all__ = [
    "AcceptanceQuery",
    "EXPECTED_ACCEPTANCE_IDS",
    "assert_rows",
    "load_acceptance_catalog",
    "validate_acceptance_catalog",
]
