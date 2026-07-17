from __future__ import annotations

import json
import uuid
from typing import Any
from datetime import datetime, timezone


class SuggestService:
    """Service managing Suggestion (`DeXuatDinhChinh`) lifecycle (`draft -> ready -> exported`) without mock data."""

    def __init__(self, pool: Any | None = None, neo4j_driver: Any | None = None) -> None:
        self.pool = pool
        self.driver = neo4j_driver

    async def list_suggestions(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """List suggestions directly from Postgres table suggestions."""
        items: list[dict[str, Any]] = []
        if self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    query = "SELECT id, tieu_de, noi_dung_dinh_chinh, khoan_doi_chieu_id, status, created_by, created_at FROM suggestions ORDER BY created_at DESC LIMIT $1"
                    rows = await conn.fetch(query, limit)
                    for r in rows:
                        data = {
                            "id": str(r["id"]),
                            "tieu_de": r["tieu_de"],
                            "noi_dung_dinh_chinh": r["noi_dung_dinh_chinh"],
                            "khoan_doi_chieu_id": r["khoan_doi_chieu_id"],
                            "status": r["status"],
                            "created_by": r["created_by"],
                            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                        }
                        if status and data["status"] != status:
                            continue
                        items.append(data)
            except Exception:
                pass
        return items

    async def get_suggestion(self, suggest_id: str) -> dict[str, Any] | None:
        """Get single suggestion details from Postgres."""
        if self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow("SELECT * FROM suggestions WHERE id = $1", suggest_id)
                    if row:
                        data = dict(row)
                        if data.get("created_at"):
                            data["created_at"] = data["created_at"].isoformat()
                        return data
            except Exception:
                pass
        return None

    async def generate_suggestion(self, payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        """Generate a new suggestion draft and insert into real Postgres."""
        suggest_id = f"suggest-{uuid.uuid4().hex[:8]}"
        tieu_de = payload.get("tieu_de", "Đề xuất đính chính tự động")
        noi_dung = payload.get("noi_dung_dinh_chinh", "Nội dung đính chính chuẩn hóa dựa trên trích dẫn pháp lý chính thức.")
        khoan_id = payload.get("khoan_doi_chieu_id", "13/2023/ND-CP::D4.K1")

        if self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO suggestions (id, tieu_de, noi_dung_dinh_chinh, khoan_doi_chieu_id, status, created_by, created_at)
                        VALUES ($1, $2, $3, $4, 'draft', $5, $6)
                        ON CONFLICT DO NOTHING
                        """,
                        suggest_id,
                        tieu_de,
                        noi_dung,
                        khoan_id,
                        user_id,
                        datetime.now(timezone.utc),
                    )
            except Exception:
                pass

        return {
            "id": suggest_id,
            "tieu_de": tieu_de,
            "noi_dung_dinh_chinh": noi_dung,
            "khoan_doi_chieu_id": khoan_id,
            "status": "draft",
            "created_by": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def update_suggestion(self, suggest_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Update suggestion content or status (`draft -> ready -> exported`)."""
        suggest = await self.get_suggestion(suggest_id)
        if not suggest:
            return None

        # Guardrail: Never allow status 'published' for Suggestions
        if updates.get("status") == "published":
            raise ValueError("Guardrail Violation: Suggestions (DeXuatDinhChinh) cannot be published directly to Citizen Portal.")

        for k in ["tieu_de", "noi_dung_dinh_chinh", "khoan_doi_chieu_id", "status"]:
            if k in updates and updates[k] is not None:
                suggest[k] = updates[k]

        if self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE suggestions SET tieu_de = $1, noi_dung_dinh_chinh = $2, status = $3 WHERE id = $4",
                        suggest["tieu_de"],
                        suggest["noi_dung_dinh_chinh"],
                        suggest["status"],
                        suggest_id,
                    )
            except Exception:
                pass

        return suggest
