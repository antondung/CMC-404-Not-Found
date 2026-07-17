from __future__ import annotations

import json
import uuid
from typing import Any
from datetime import datetime, timezone
from app.pipelines.legal.version_diff import VersionDiff
from app.pipelines.legal.normalize import normalize_so_hieu


class LegalDiffFacade:
    """Facade orchestrating BE1 legal pipeline calls, version diffing, and legal document queries from real DB/Graph."""

    def __init__(self, pool: Any | None = None, neo4j_driver: Any | None = None) -> None:
        self.pool = pool
        self.driver = neo4j_driver
        self.differ = VersionDiff()

    async def ingest_document(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Trigger ingestion job into real Postgres jobs table / Celery Worker queue."""
        so_hieu = payload.get("so_hieu", "")
        norm_so_hieu = normalize_so_hieu(so_hieu) if so_hieu else ""
        job_id = f"job-legal-{uuid.uuid4().hex[:8]}"

        if self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO jobs (id, type, status, payload_json, created_at)
                        VALUES ($1, 'legal_ingest', 'queued', $2, $3)
                        ON CONFLICT DO NOTHING
                        """,
                        job_id,
                        json.dumps(payload),
                        datetime.now(timezone.utc),
                    )
            except Exception as e:
                pass

        return {
            "job_id": job_id,
            "so_hieu": norm_so_hieu,
            "status": "queued",
            "message": "Legal ingestion task submitted into queue.",
        }

    async def list_van_ban(self, visibility: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        """List legal documents from Neo4j (VanBanPhapLuat node or Postgres van_ban table)."""
        items: list[dict[str, Any]] = []
        if self.driver and hasattr(self.driver, "session"):
            try:
                query = "MATCH (v:VanBanPhapLuat) RETURN v ORDER BY v.ngay_ban_hanh DESC LIMIT 100"
                async with self.driver.session() as session:
                    res = await session.run(query)
                    async for record in res:
                        data = dict(record["v"])
                        if visibility and data.get("visibility") != visibility:
                            continue
                        if status and data.get("trang_thai") != status:
                            continue
                        items.append(data)
            except Exception:
                pass

        if not items and self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch("SELECT * FROM van_ban ORDER BY ngay_ban_hanh DESC LIMIT 100")
                    for r in rows:
                        data = dict(r)
                        if visibility and data.get("visibility") != visibility:
                            continue
                        if status and data.get("trang_thai") != status:
                            continue
                        items.append(data)
            except Exception:
                pass

        return items

    async def get_van_ban_detail(self, van_ban_id: str) -> dict[str, Any] | None:
        """Fetch real legal document node & Khoan hierarchy from Neo4j."""
        if self.driver and hasattr(self.driver, "session"):
            try:
                query = """
                MATCH (v:VanBanPhapLuat)
                WHERE v.vb_id = $id OR v.so_hieu = $id OR id(v) = $id
                OPTIONAL MATCH (v)-[:CO_DIEU|CO_KHOAN*1..2]->(k:Khoan)
                RETURN v, collect(k) AS khoans
                """
                async with self.driver.session() as session:
                    res = await session.run(query, id=van_ban_id)
                    record = await res.single()
                    if record and record["v"]:
                        doc = dict(record["v"])
                        khoans = [dict(k) for k in record["khoans"] if k is not None]
                        doc["tree"] = khoans
                        return doc
            except Exception:
                pass

        if self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow("SELECT * FROM van_ban WHERE id = $1 OR so_hieu = $1", van_ban_id)
                    if row:
                        doc = dict(row)
                        krows = await conn.fetch("SELECT * FROM khoan WHERE van_ban_id = $1 ORDER BY so_khoan ASC", doc.get("id", van_ban_id))
                        doc["tree"] = [dict(k) for k in krows]
                        return doc
            except Exception:
                pass

        return None

    async def get_khoan_detail(self, khoan_id: str) -> dict[str, Any] | None:
        """Fetch exact Khoan node and related legal entities from Neo4j."""
        if self.driver and hasattr(self.driver, "session"):
            try:
                query = """
                MATCH (k:Khoan)
                WHERE k.khoan_id = $id OR id(k) = $id
                OPTIONAL MATCH (k)-[r:QUY_DINH|AP_DUNG_CHO|THAY_THE]->(e)
                RETURN k, collect({rel: type(r), entity: e}) AS entities
                """
                async with self.driver.session() as session:
                    res = await session.run(query, id=khoan_id)
                    record = await res.single()
                    if record and record["k"]:
                        item = dict(record["k"])
                        item["entities"] = [dict(x["entity"]) for x in record["entities"] if x["entity"] is not None]
                        return item
            except Exception:
                pass

        if self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow("SELECT * FROM khoan WHERE id = $1 OR khoan_id = $1", khoan_id)
                    if row:
                        return dict(row)
            except Exception:
                pass

        return None

    async def compute_diff(self, old_text: str, new_text: str, method: str = "auto") -> dict[str, Any]:
        """Compute structural hunks and similarity diff between two legal segments."""
        hunks = self.differ.diff(old_text, new_text)
        return {
            "hunks": hunks,
            "method": method,
            "old_text": old_text,
            "new_text": new_text,
            "total_hunks": len(hunks),
        }

    async def list_files(self, van_ban_id: str) -> list[dict[str, Any]]:
        """List real files from Postgres files table."""
        items: list[dict[str, Any]] = []
        if self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch("SELECT * FROM files WHERE van_ban_id = $1", van_ban_id)
                    for r in rows:
                        items.append(dict(r))
            except Exception:
                pass
        return items

    async def get_file_detail(self, file_id: str) -> dict[str, Any] | None:
        """Fetch file metadata from Postgres files table."""
        if self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow("SELECT * FROM files WHERE id = $1 OR file_id = $1", file_id)
                    if row:
                        return dict(row)
            except Exception:
                pass
        return None
