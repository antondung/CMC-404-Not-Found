from __future__ import annotations

from typing import Any
from app.schemas import CandidateKhoan


class Neo4jLegalRepository:
    """Read-only legal repository over Neo4j Khoan nodes (source of truth for canonical text).

    Implements the LegalRepository protocol used by brief/suggest generation pipelines.
    """

    def __init__(self, driver: Any) -> None:
        self.driver = driver

    @staticmethod
    def _to_candidate(record: Any) -> CandidateKhoan:
        return CandidateKhoan(
            khoan_id=str(record["khoan_id"]),
            noi_dung=str(record["noi_dung"] or ""),
            score=1.0,
        )

    async def get_khoan(self, khoan_id: str) -> CandidateKhoan | None:
        if not self.driver or not hasattr(self.driver, "session"):
            return None
        query = "MATCH (k:Khoan {khoan_id: $id}) RETURN k.khoan_id AS khoan_id, k.noi_dung AS noi_dung"
        async with self.driver.session() as session:
            res = await session.run(query, id=khoan_id)
            record = await res.single()
        if not record or not record["khoan_id"] or not record["noi_dung"]:
            return None
        return self._to_candidate(record)

    async def get_khoan_many(self, khoan_ids: list[str]) -> list[CandidateKhoan]:
        if not khoan_ids or not self.driver or not hasattr(self.driver, "session"):
            return []
        query = (
            "MATCH (k:Khoan) WHERE k.khoan_id IN $ids "
            "RETURN k.khoan_id AS khoan_id, k.noi_dung AS noi_dung"
        )
        out: list[CandidateKhoan] = []
        async with self.driver.session() as session:
            res = await session.run(query, ids=list(khoan_ids))
            async for record in res:
                if record["khoan_id"] and record["noi_dung"]:
                    out.append(self._to_candidate(record))
        return out

    async def list_khoan_for_van_ban(self, van_ban_id: str) -> list[CandidateKhoan]:
        if not van_ban_id or not self.driver or not hasattr(self.driver, "session"):
            return []
        # Ưu tiên traversal cấu trúc; fallback theo thuộc tính van_ban_id trên Khoan.
        query = (
            "MATCH (v:VanBanPhapLuat) WHERE v.vb_id = $vb OR v.so_hieu = $vb "
            "MATCH (v)-[:CO_DIEU]->(:Dieu)-[:CO_KHOAN]->(k:Khoan) "
            "RETURN k.khoan_id AS khoan_id, k.noi_dung AS noi_dung "
            "UNION "
            "MATCH (k:Khoan {van_ban_id: $vb}) "
            "RETURN k.khoan_id AS khoan_id, k.noi_dung AS noi_dung"
        )
        out: list[CandidateKhoan] = []
        seen: set[str] = set()
        async with self.driver.session() as session:
            res = await session.run(query, vb=van_ban_id)
            async for record in res:
                kid = record["khoan_id"]
                if kid and record["noi_dung"] and kid not in seen:
                    seen.add(str(kid))
                    out.append(self._to_candidate(record))
        return out
