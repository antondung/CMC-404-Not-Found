"""Load the deterministic synthetic LAWGIC fixture into localhost datastores."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
load_dotenv(_BACKEND / ".env")

from app.evaluation.integration_fixture import (
    CANDIDATE_ID,
    COMMIT_KEY,
    EVENT_ID,
    FIXTURE_ID,
    LOGICAL_VB_ID,
    REVIEW_ID,
    fixture_config,
    fixture_versions,
)
from app.pipelines.legal.provision_index import (
    LEGAL_PROVISION_COLLECTION,
    deterministic_provision_point_id,
    legal_provision_payload,
)


def _require_local(name: str, value: str | None) -> str:
    raw = str(value or "").strip()
    host = (urlparse(raw).hostname or "").lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError(f"{name} must target localhost, received host={host!r}")
    return raw


def _rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for version in fixture_versions():
        row = version.model_dump(mode="json")
        row["fixture_id"] = FIXTURE_ID
        rows.append(row)
    return rows


async def _load_neo4j(driver: Any, rows: list[dict[str, Any]]) -> None:
    source_rows = [
        {
            "vb_id": f"{LOGICAL_VB_ID}-{suffix}",
            "so_hieu": f"LAWGIC-FIXTURE-{suffix}",
            "fixture_id": FIXTURE_ID,
        }
        for suffix in ("V1", "V2", "V3")
    ]

    async def write(tx: Any) -> None:
        result = await tx.run(
            """
            UNWIND $rows AS row
            MERGE (document:VanBanPhapLuat {vb_id: row.vb_id})
            SET document.so_hieu = row.so_hieu,
                document.ten = 'Văn bản fixture LAWGIC',
                document.visibility = 'public',
                document.fixture_id = row.fixture_id
            """,
            rows=source_rows,
        )
        await result.consume()
        labels = {"dieu": "Dieu", "khoan": "Khoan", "diem": "Diem"}
        for level, label in labels.items():
            level_rows = [row for row in rows if row["level"] == level]
            result = await tx.run(
                f"""
                UNWIND $rows AS row
                MERGE (p:LegalProvision:{label} {{provision_id: row.provision_id}})
                SET p.lineage_id = row.lineage_id,
                    p.parent_lineage_id = row.parent_lineage_id,
                    p.level = row.level,
                    p.version_no = row.version_no,
                    p.so = row.article,
                    p.so_dieu = row.article,
                    p.so_khoan = row.clause,
                    p.ky_hieu = row.point,
                    p.noi_dung = row.text,
                    p.tieu_de = row.text,
                    p.effective_from = date(row.effective_from),
                    p.effective_to = CASE WHEN row.effective_to IS NULL THEN null ELSE date(row.effective_to) END,
                    p.text_checksum = row.text_checksum,
                    p.source_checksum = row.source_checksum,
                    p.source_vb_id = row.source_vb_id,
                    p.logical_vb_id = row.logical_vb_id,
                    p.visibility = 'public',
                    p.review_status = 'approved',
                    p.recorded_at = datetime(row.recorded_at),
                    p.fixture_id = row.fixture_id,
                    p.dieu_id = CASE WHEN row.level = 'dieu' THEN row.provision_id ELSE p.dieu_id END,
                    p.khoan_id = CASE WHEN row.level = 'khoan' THEN row.provision_id ELSE p.khoan_id END,
                    p.diem_id = CASE WHEN row.level = 'diem' THEN row.provision_id ELSE p.diem_id END
                WITH p, row
                MATCH (document:VanBanPhapLuat {{vb_id: row.source_vb_id}})
                FOREACH (_ IN CASE WHEN row.level = 'dieu' THEN [1] ELSE [] END |
                  MERGE (document)-[:CO_DIEU]->(p)
                )
                """,
                rows=level_rows,
            )
            await result.consume()
        for relationship, child_level in (("CO_KHOAN", "khoan"), ("CO_DIEM", "diem")):
            result = await tx.run(
                f"""
                MATCH (child:LegalProvision {{fixture_id: $fixture_id, level: $child_level}})
                MATCH (parent:LegalProvision {{fixture_id: $fixture_id, lineage_id: child.parent_lineage_id}})
                MERGE (parent)-[:{relationship}]->(child)
                """,
                fixture_id=FIXTURE_ID,
                child_level=child_level,
            )
            await result.consume()

        point_a = sorted(
            [row for row in rows if row["level"] == "diem" and row["point"] == "a"],
            key=lambda row: row["version_no"],
        )
        for old, new in zip(point_a, point_a[1:]):
            result = await tx.run(
                """
                MATCH (old:LegalProvision {provision_id: $old_id})
                MATCH (new:LegalProvision {provision_id: $new_id})
                MERGE (old)-[edge:SUPERSEDED_BY]->(new)
                SET edge.review_id = $review_id,
                    edge.commit_key = $commit_key,
                    edge.change_type = 'REWORDED',
                    edge.committed_by = coalesce(edge.committed_by, 'fixture-committer'),
                    edge.committed_at = coalesce(edge.committed_at, datetime()),
                    edge.fixture_id = $fixture_id
                """,
                old_id=old["provision_id"],
                new_id=new["provision_id"],
                review_id=REVIEW_ID,
                commit_key=COMMIT_KEY,
                fixture_id=FIXTURE_ID,
            )
            await result.consume()
        result = await tx.run(
            """
            MATCH (old:LegalProvision {provision_id: $old_id})
            MATCH (source:VanBanPhapLuat {vb_id: $source_vb_id})
            MERGE (old)-[edge:AMENDED_BY]->(source)
            SET edge.review_id = $review_id,
                edge.commit_key = $commit_key,
                edge.change_type = 'REWORDED',
                edge.committed_by = coalesce(edge.committed_by, 'fixture-committer'),
                edge.committed_at = coalesce(edge.committed_at, datetime()),
                edge.fixture_id = $fixture_id
            """,
            old_id=point_a[0]["provision_id"],
            source_vb_id=f"{LOGICAL_VB_ID}-V2",
            review_id=REVIEW_ID,
            commit_key=COMMIT_KEY,
            fixture_id=FIXTURE_ID,
        )
        await result.consume()
        result = await tx.run(
            """
            MATCH (old:LegalProvision {provision_id: $old_id})
            MATCH (current:LegalProvision {provision_id: $current_id})
            MERGE (content:BaiDang:NoiDungNguon {content_id: 'lawgic-fixture-content'})
            SET content.fixture_id = $fixture_id
            MERGE (claim:YKien {uuid: 'lawgic-fixture-claim'})
            SET claim.noi_dung = 'Ngưỡng áp dụng là 200 triệu đồng.', claim.fixture_id = $fixture_id
            MERGE (content)-[:CO_YKIEN]->(claim)
            MERGE (misconception:Misconception {uuid: 'lawgic-fixture-misconception'})
            SET misconception.fixture_id = $fixture_id
            MERGE (claim)-[instance:INSTANCE_OF]->(misconception)
            SET instance.content_id = content.content_id,
                instance.canonical_url = 'https://example.test/lawgic-fixture',
                instance.content_hash = 'lawgic-fixture-content-hash',
                instance.published_at = datetime('2026-06-20T00:00:00Z'),
                instance.evidence_start = 0,
                instance.evidence_end = 37
            MERGE (misconception)-[:CONTRADICTS]->(current)
            MERGE (evaluation:TemporalMisconceptionEvaluation {evaluation_id: 'lawgic-fixture-evaluation'})
            SET evaluation.verdict = 'OUTDATED_BUT_PREVIOUSLY_TRUE',
                evaluation.historical_label = 'khop',
                evaluation.current_label = 'mau_thuan',
                evaluation.historical_checksum = old.text_checksum,
                evaluation.current_checksum = current.text_checksum,
                evaluation.historical_lineage_id = old.lineage_id,
                evaluation.current_lineage_id = current.lineage_id,
                evaluation.fixture_id = $fixture_id
            MERGE (claim)-[:HAS_TEMPORAL_EVALUATION]->(evaluation)
            MERGE (evaluation)-[:HISTORICAL_BASIS]->(old)
            MERGE (evaluation)-[:CURRENT_BASIS]->(current)
            """,
            old_id=point_a[0]["provision_id"],
            current_id=point_a[1]["provision_id"],
            fixture_id=FIXTURE_ID,
        )
        await result.consume()

    async with driver.session() as session:
        await session.execute_write(write)


async def _load_postgres(pool: Any, rows: list[dict[str, Any]]) -> None:
    point_a = sorted(
        [row for row in rows if row["level"] == "diem" and row["point"] == "a"],
        key=lambda row: row["version_no"],
    )
    async with pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                """
                INSERT INTO amendment_review_batches (
                  id, target_logical_vb_id, amendment_text, status, idempotency_key,
                  request_hash, preview_snapshot, created_by, submitted_by, submitted_at,
                  reviewed_by, reviewed_at, review_note, revision,
                  commit_idempotency_key, committed_by, committed_at, commit_result
                ) VALUES (
                  $1::uuid, $2, $3, 'committed', $4, $5, $6::jsonb,
                  'fixture-loader', 'fixture-loader', now(), 'fixture-reviewer', now(),
                  'Synthetic local integration fixture', 1, $7, 'fixture-committer', now(), $8::jsonb
                )
                ON CONFLICT (id) DO UPDATE SET
                  status = 'committed', reviewed_by = EXCLUDED.reviewed_by,
                  reviewed_at = EXCLUDED.reviewed_at,
                  commit_idempotency_key = EXCLUDED.commit_idempotency_key,
                  committed_by = EXCLUDED.committed_by,
                  committed_at = EXCLUDED.committed_at,
                  commit_result = EXCLUDED.commit_result
                """,
                REVIEW_ID,
                LOGICAL_VB_ID,
                "Sửa ngưỡng áp dụng từ 200 triệu đồng thành 500 triệu đồng.",
                "lawgic-fixture-review-v1",
                "a" * 64,
                json.dumps({"fixture_id": FIXTURE_ID}),
                COMMIT_KEY,
                json.dumps({"fixture_id": FIXTURE_ID, "status": "committed"}),
            )
            await connection.execute(
                """
                INSERT INTO amendment_review_candidates (
                  id, batch_id, old_provision_id, new_provision_id, lineage_id,
                  confidence, change_type, review_route, proposed_effective_from,
                  decision, reviewed_by, reviewed_at
                ) VALUES (
                  $1::uuid, $2::uuid, $3, $4, $5, 1.0, 'REWORDED',
                  'human_review', date('2026-07-01'), 'accepted', 'fixture-reviewer', now()
                )
                ON CONFLICT (id) DO NOTHING
                """,
                CANDIDATE_ID,
                REVIEW_ID,
                point_a[0]["provision_id"],
                point_a[1]["provision_id"],
                point_a[0]["lineage_id"],
            )
            await connection.execute(
                """
                INSERT INTO amendment_review_events (
                  id, batch_id, actor_id, action, from_status, to_status, payload
                ) VALUES (
                  $1::uuid, $2::uuid, 'fixture-committer', 'graph_commit_reconciled',
                  'approved', 'committed', $3::jsonb
                )
                ON CONFLICT (id) DO NOTHING
                """,
                EVENT_ID,
                REVIEW_ID,
                json.dumps({"fixture_id": FIXTURE_ID, "commit_key": COMMIT_KEY}),
            )


async def _load_qdrant(raw_client: Any, rows: list[dict[str, Any]]) -> None:
    from qdrant_client import models

    if not await raw_client.collection_exists(LEGAL_PROVISION_COLLECTION):
        await raw_client.create_collection(
            collection_name=LEGAL_PROVISION_COLLECTION,
            vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE),
        )
    parent_lineages = {row["parent_lineage_id"] for row in rows if row["parent_lineage_id"]}
    leaves = [row for row in rows if row["lineage_id"] not in parent_lineages]
    points = [
        models.PointStruct(
            id=deterministic_provision_point_id(row["provision_id"]),
            vector=[0.0] * 1536,
            payload=legal_provision_payload(row),
        )
        for row in leaves
    ]
    await raw_client.upsert(collection_name=LEGAL_PROVISION_COLLECTION, points=points, wait=True)


async def _run(output_config: Path) -> dict[str, Any]:
    from neo4j import AsyncGraphDatabase
    from qdrant_client import AsyncQdrantClient
    import asyncpg

    neo4j_uri = _require_local("NEO4J_URI", os.getenv("NEO4J_URI"))
    postgres_url = _require_local("DATABASE_URL", os.getenv("DATABASE_URL"))
    qdrant_url = _require_local("QDRANT_URL", os.getenv("QDRANT_URL"))
    driver = AsyncGraphDatabase.driver(
        neo4j_uri,
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password")),
    )
    pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=1)
    qdrant = AsyncQdrantClient(url=qdrant_url, timeout=30.0)
    try:
        rows = _rows()
        await _load_neo4j(driver, rows)
        await _load_postgres(pool, rows)
        await _load_qdrant(qdrant, rows)
        config = fixture_config()
        output_config.parent.mkdir(parents=True, exist_ok=True)
        output_config.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "fixture_id": FIXTURE_ID,
            "neo4j_versions": len(rows),
            "qdrant_leaves": len(
                [row for row in rows if row["lineage_id"] not in {item["parent_lineage_id"] for item in rows if item["parent_lineage_id"]}]
            ),
            "postgres_review_id": REVIEW_ID,
            "output_config": str(output_config),
            "mutated": True,
        }
    finally:
        await qdrant.close()
        await pool.close()
        await driver.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Load the localhost-only synthetic LAWGIC integration fixture.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument(
        "--output-config",
        type=Path,
        default=Path("eval/config/integration-fixture.local.json"),
    )
    args = parser.parse_args()
    if not (args.apply and args.yes):
        print(json.dumps({"status": "dry_run", "mutated": False, "fixture_id": FIXTURE_ID}))
        return 0
    try:
        report = asyncio.run(_run(args.output_config))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "mutated": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"status": "loaded", **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
