"""Run fail-closed, read-only LAWGIC acceptance across all canonical datastores."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
load_dotenv(_BACKEND / ".env")

from app.adapters.qdrant_vector import QdrantVectorClient
from app.evaluation.integration_acceptance import (
    run_integration_acceptance,
    validate_integration_config,
)
from app.evaluation.lawgic_quality import EvaluationError


def _load_config(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"invalid integration config: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvaluationError("integration config must be an object")
    return payload


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    config = _load_config(args.integration_config)
    validate_integration_config(config)

    from neo4j import AsyncGraphDatabase
    from qdrant_client import AsyncQdrantClient
    import asyncpg

    neo4j_uri = os.getenv("NEO4J_URI") or os.getenv("NEO4J_URL")
    neo4j_user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    postgres_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    qdrant_url = os.getenv("QDRANT_URL")
    missing = [
        name
        for name, value in (
            ("NEO4J_URI", neo4j_uri),
            ("NEO4J_USER", neo4j_user),
            ("NEO4J_PASSWORD", neo4j_password),
            ("DATABASE_URL", postgres_url),
            ("QDRANT_URL", qdrant_url),
        )
        if not value
    ]
    if missing:
        raise EvaluationError(f"missing datastore configuration: {', '.join(missing)}")

    driver = AsyncGraphDatabase.driver(
        str(neo4j_uri),
        auth=(str(neo4j_user), str(neo4j_password)),
    )
    postgres_pool = None
    raw_qdrant = AsyncQdrantClient(url=str(qdrant_url), timeout=15.0)
    try:
        await driver.verify_connectivity()
        postgres_pool = await asyncpg.create_pool(
            str(postgres_url),
            min_size=1,
            max_size=1,
            server_settings={"default_transaction_read_only": "on"},
        )
        return await run_integration_acceptance(
            driver=driver,
            postgres_pool=postgres_pool,
            qdrant=QdrantVectorClient(raw_qdrant),
            catalog_path=args.catalog,
            config=config,
        )
    finally:
        if postgres_pool is not None:
            await postgres_pool.close()
        await raw_qdrant.close()
        await driver.close()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Run read-only LAWGIC acceptance across Neo4j, PostgreSQL and Qdrant."
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("Data/schema/acceptance_queries.cypher"),
    )
    parser.add_argument("--integration-config", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 - CLI must persist fail-closed evidence
        report = {
            "mode": "read_only_integration_acceptance",
            "passed": False,
            "mutated": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
