from __future__ import annotations

import json
import uuid
from typing import Any
from datetime import datetime, timezone
from app.core.security import UserToken
from app.services.publish_gate import PublishGateService


class BriefService:
    """Service managing Content Briefs (`BaiTomTat`) lifecycle and transitions."""

    def __init__(self, pool: Any | None = None, neo4j_driver: Any | None = None) -> None:
        self.pool = pool
        self.driver = neo4j_driver
        self.gate = PublishGateService(pool=pool, neo4j_driver=neo4j_driver)

    async def list_briefs(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """List content briefs with status filtering."""
        items: list[dict[str, Any]] = []
        if self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    query = "SELECT id, tieu_de, noi_dung, media_types, status, citations_json, created_by, created_at, published_at FROM briefs ORDER BY created_at DESC LIMIT $1"
                    rows = await conn.fetch(query, limit)
                    for r in rows:
                        cits = r["citations_json"] if "citations_json" in r else None
                        if isinstance(cits, str):
                            cits = json.loads(cits)
                        if status and r["status"] != status:
                            continue
                        items.append({
                            "id": str(r["id"]),
                            "tieu_de": r["tieu_de"],
                            "noi_dung": r["noi_dung"],
                            "media_types": r["media_types"] or ["article"],
                            "status": r["status"],
                            "citations": cits or [],
                            "created_by": r["created_by"],
                            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                            "published_at": r["published_at"].isoformat() if r.get("published_at") else None,
                        })
                    if items:
                        return items
            except Exception:
                pass

        sample = [
            {
                "id": "brief-101",
                "tieu_de": "Tóm tắt điểm mới của Nghị định 13/2023/NĐ-CP về Bảo vệ Dữ liệu Cá nhân",
                "noi_dung": "Nghị định 13/2023 quy định chi tiết quyền và nghĩa vụ của chủ thể dữ liệu, các biện pháp bảo vệ và chế tài xử phạt khi vi phạm.",
                "media_types": ["article", "infographic"],
                "status": "published",
                "citations": [
                    {
                        "khoan_id": "13/2023/ND-CP::D4.K1",
                        "quote": "Quy định nguyên văn mẫu trong Neo4j.",
                        "van_ban": "Nghị định 13/2023/NĐ-CP",
                        "dieu": "Điều 4",
                    }
                ],
                "created_by": "user-truyen-thong-1",
                "created_at": "2026-07-16T10:00:00Z",
                "published_at": "2026-07-16T12:00:00Z",
            },
            {
                "id": "brief-102",
                "tieu_de": "Quy định kê khai thuế thu nhập cá nhân đúng hạn",
                "noi_dung": "Bài tóm tắt hướng dẫn người nộp thuế thực hiện thủ tục kê khai online theo Nghị định 15/2020.",
                "media_types": ["article", "qa"],
                "status": "draft",
                "citations": [
                    {
                        "khoan_id": "15/2020/ND-CP::D1.K1",
                        "quote": "Người nộp thuế phải kê khai đúng hạn theo quy định tại Khoản 15/2020/ND-CP::D1.K1.",
                        "van_ban": "Nghị định 15/2020/NĐ-CP",
                        "dieu": "Điều 1",
                    }
                ],
                "created_by": "user-truyen-thong-1",
                "created_at": "2026-07-17T08:00:00Z",
                "published_at": None,
            },
            {
                "id": "brief-no-cit",
                "tieu_de": "Bài tóm tắt chưa đủ trích dẫn (nháp)",
                "noi_dung": "Bài viết này đang thiếu trích dẫn cụ thể sang Khoản.",
                "media_types": ["article"],
                "status": "draft",
                "citations": [],
                "created_by": "user-truyen-thong-1",
                "created_at": "2026-07-17T08:30:00Z",
                "published_at": None,
            },
        ]
        if status:
            sample = [x for x in sample if x["status"] == status]
        return sample

    async def get_brief(self, brief_id: str) -> dict[str, Any] | None:
        """Get single brief details."""
        items = await self.list_briefs()
        for x in items:
            if x["id"] == brief_id:
                return x
        return None

    async def generate_brief(self, payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        """Generate a new content brief from retrieved Khoan context."""
        brief_id = f"brief-{uuid.uuid4().hex[:8]}"
        tieu_de = payload.get("tieu_de", "Bài tóm tắt pháp lý tự động")
        noi_dung = payload.get("noi_dung", "Nội dung tóm tắt được tổng hợp từ các trích dẫn pháp lý đáng tin cậy.")
        citations = payload.get("citations", [
            {"khoan_id": "15/2020/ND-CP::D1.K1", "quote": "Người nộp thuế phải kê khai đúng hạn theo quy định tại Khoản 15/2020/ND-CP::D1.K1."}
        ])
        media_types = payload.get("media_types", ["article"])

        if self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO briefs (id, tieu_de, noi_dung, media_types, status, citations_json, created_by, created_at)
                        VALUES ($1, $2, $3, $4, 'draft', $5, $6, $7)
                        ON CONFLICT DO NOTHING
                        """,
                        brief_id,
                        tieu_de,
                        noi_dung,
                        media_types,
                        json.dumps(citations),
                        user_id,
                        datetime.now(timezone.utc),
                    )
            except Exception:
                pass

        return {
            "id": brief_id,
            "tieu_de": tieu_de,
            "noi_dung": noi_dung,
            "media_types": media_types,
            "status": "draft",
            "citations": citations,
            "created_by": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def update_brief(self, brief_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Update brief title, content, citations, or media types."""
        brief = await self.get_brief(brief_id)
        if not brief:
            return None

        for k in ["tieu_de", "noi_dung", "media_types", "citations", "status"]:
            if k in updates and updates[k] is not None:
                brief[k] = updates[k]

        if self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE briefs SET tieu_de = $1, noi_dung = $2, status = $3 WHERE id = $4",
                        brief["tieu_de"],
                        brief["noi_dung"],
                        brief["status"],
                        brief_id,
                    )
            except Exception:
                pass

        return brief

    async def publish_brief(self, brief_id: str, actor: UserToken) -> tuple[bool, dict[str, Any], list[str]]:
        """Trigger PublishGate verification and publish."""
        brief = await self.get_brief(brief_id)
        if not brief:
            return False, {}, [f"Brief {brief_id} không tồn tại"]
        return await self.gate.verify_and_publish_brief(brief_id, actor, brief)

    async def archive_brief(self, brief_id: str, actor: UserToken) -> dict[str, Any] | None:
        """Archive a brief."""
        brief = await self.get_brief(brief_id)
        if not brief:
            return None
        brief["status"] = "archived"
        if self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute("UPDATE briefs SET status = 'archived' WHERE id = $1", brief_id)
            except Exception:
                pass
        return brief
