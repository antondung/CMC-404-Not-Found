from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evaluation.acceptance_catalog import (
    EXPECTED_ACCEPTANCE_IDS,
    assert_rows,
    load_acceptance_catalog,
    validate_acceptance_catalog,
)
from app.evaluation.lawgic_quality import EvaluationError


def _load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EvaluationError("integration config must be an object")
    checks = payload.get("checks")
    if not isinstance(checks, dict):
        raise EvaluationError("integration config requires a checks object")
    missing = sorted(set(EXPECTED_ACCEPTANCE_IDS) - set(checks))
    unexpected = sorted(set(checks) - set(EXPECTED_ACCEPTANCE_IDS))
    if missing or unexpected:
        raise EvaluationError(f"integration checks mismatch; missing={missing}, unexpected={unexpected}")
    return payload


def _run_integration(catalog_path: Path, config_path: Path) -> dict[str, Any]:
    from neo4j import GraphDatabase, READ_ACCESS

    catalog = load_acceptance_catalog(catalog_path)
    config = _load_config(config_path)
    uri = os.getenv("NEO4J_URI") or os.getenv("NEO4J_URL")
    username = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri or not username or not password:
        raise EvaluationError("integration mode requires NEO4J_URI, NEO4J_USER and NEO4J_PASSWORD")
    results: list[dict[str, Any]] = []
    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        driver.verify_connectivity()
        with driver.session(
            database=config.get("database"),
            default_access_mode=READ_ACCESS,
        ) as session:
            for check_id in EXPECTED_ACCEPTANCE_IDS:
                spec = config["checks"][check_id]
                params = spec.get("params") or {}
                assertion = spec.get("assertion") or {}
                records = session.run(catalog[check_id].query, **params)
                rows = [record.data() for record in records]
                passed, message = assert_rows(rows, assertion)
                results.append(
                    {
                        "check_id": check_id,
                        "passed": passed,
                        "row_count": len(rows),
                        "assertion": assertion,
                        "message": message,
                    }
                )
    finally:
        driver.close()
    return {
        "mode": "read_only_integration",
        "catalog": str(catalog_path),
        "results": results,
        "passed": all(item["passed"] for item in results),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or run the T01-T20/N01-N02 acceptance catalog.")
    parser.add_argument("--catalog", type=Path, default=Path("Data/schema/acceptance_queries.cypher"))
    parser.add_argument("--integration-config", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = (
            _run_integration(args.catalog, args.integration_config)
            if args.integration_config
            else {"mode": "catalog_validation", **validate_acceptance_catalog(args.catalog)}
        )
    except (EvaluationError, OSError, json.JSONDecodeError) as exc:
        report = {"passed": False, "error": str(exc)}
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report.get("passed", report.get("valid", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
