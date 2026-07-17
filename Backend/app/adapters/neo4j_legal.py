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

    async def upsert_van_ban(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Write/merge a legal document tree (VanBanPhapLuat -> Dieu -> Khoan) into Neo4j.

        `doc` must contain metadata plus `dieu_list`, where each Dieu carries `dieu_id`,
        `so`, `tieu_de`, and `khoan_list` (each with `khoan_id`, `so`, `noi_dung`).
        Merge keys match Data/schema/neo4j_constraints.cypher (vb_id/dieu_id/khoan_id).
        """
        if not self.driver or not hasattr(self.driver, "session"):
            return {"written": False, "reason": "neo4j_unavailable"}

        dieu_list = doc.get("dieu_list", [])
        query = """
        MERGE (v:VanBanPhapLuat {vb_id: $vb_id})
        SET v.so_hieu = $so_hieu, v.ten = $ten, v.loai = $loai,
            v.ngay_ban_hanh = $ngay_ban_hanh, v.ngay_hieu_luc = $ngay_hieu_luc,
            v.trang_thai = $trang_thai, v.visibility = $visibility,
            v.co_quan_ban_hanh = $co_quan_ban_hanh
        WITH v
        UNWIND $dieu_list AS d
          MERGE (dieu:Dieu {dieu_id: d.dieu_id})
          SET dieu.so = d.so, dieu.tieu_de = d.tieu_de,
              dieu.van_ban_id = $vb_id, dieu.visibility = $visibility
          MERGE (v)-[:CO_DIEU]->(dieu)
          WITH v, dieu, d
          UNWIND d.khoan_list AS k
            MERGE (kh:Khoan {khoan_id: k.khoan_id})
            SET kh.so = k.so, kh.noi_dung = k.noi_dung, kh.van_ban_id = $vb_id,
                kh.dieu_id = d.dieu_id, kh.visibility = $visibility
            MERGE (dieu)-[:CO_KHOAN]->(kh)
        """
        params = {
            "vb_id": doc.get("vb_id"),
            "so_hieu": doc.get("so_hieu"),
            "ten": doc.get("ten"),
            "loai": doc.get("loai"),
            "ngay_ban_hanh": doc.get("ngay_ban_hanh"),
            "ngay_hieu_luc": doc.get("ngay_hieu_luc"),
            "trang_thai": doc.get("trang_thai", "hieu_luc"),
            "visibility": doc.get("visibility", "public"),
            "co_quan_ban_hanh": doc.get("co_quan_ban_hanh"),
            "dieu_list": dieu_list,
        }
        async with self.driver.session() as session:
            await session.run(query, **params)

        khoan_count = sum(len(d.get("khoan_list", [])) for d in dieu_list)
        return {"written": True, "vb_id": doc.get("vb_id"), "dieu_count": len(dieu_list), "khoan_count": khoan_count}

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
