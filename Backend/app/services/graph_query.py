from __future__ import annotations

import math
from typing import Any

import logging
import json
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_TYPE_PRIORITY = (
    "VanBanPhapLuat", "VanBan", "Chuong", "Dieu", "Khoan", "ChuDe", "BaiDang", "YKien",
)
_TYPE_ALIASES = {
    "VanBanPhapLuat": "van_ban", "VanBan": "van_ban", "Chuong": "chuong",
    "Dieu": "dieu", "Khoan": "khoan", "ChuDe": "chu_de",
}
_LEGAL_LEVEL_SCORE = {"van_ban": 100, "chuong": 70, "dieu": 50, "khoan": 30, "chu_de": 40}

class GraphNodeEnrichment(BaseModel):
    short_label: str = Field(min_length=1, max_length=80)
    topic: str | None = Field(default=None, max_length=120)
    keywords: list[str] = Field(default_factory=list, max_length=8)
    semantic_relevance: float | None = Field(default=None, ge=0, le=1)
    cluster_label: str | None = Field(default=None, max_length=120)

def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    iso = getattr(value, "isoformat", None)
    if callable(iso):
        try:
            return iso()
        except Exception:  # noqa: BLE001
            pass
    return str(value)

def _node_type(node: Any) -> tuple[str, str]:
    labels = set(node.labels) if hasattr(node, "labels") else set()
    raw = next((label for label in _TYPE_PRIORITY if label in labels), sorted(labels)[0] if labels else "Node")
    return raw, _TYPE_ALIASES.get(raw, raw.lower())

def _node_key(node: Any) -> str:
    return str(
        node.get("vb_id")
        or node.get("khoan_id")
        or node.get("dieu_id")
        or node.get("bai_dang_id")
        or node.get("slug")
        or node.get("id")
        or getattr(node, "element_id", None)
        or "unknown"
    )

def _node_label(node: Any, raw_type: str | None = None) -> str:
    """Return a stable graph label; never expose long legal/person content as a node name."""
    raw_type = raw_type or _node_type(node)[0]
    if raw_type in {"VanBanPhapLuat", "VanBan"}:
        return str(node.get("so_hieu") or node.get("ten") or _node_key(node))[:90]
    if raw_type == "Chuong":
        return f"Chương {node.get('so') or node.get('so_chuong') or _node_key(node)}"[:90]
    if raw_type == "Dieu":
        number = node.get("so") or node.get("so_dieu")
        return f"Điều {number}" if number else str(node.get("dieu_id") or _node_key(node))[:90]
    if raw_type == "Khoan":
        number = node.get("so") or node.get("so_khoan")
        return f"Khoản {number}" if number else str(node.get("khoan_id") or _node_key(node))[:90]
    return str(node.get("ten") or node.get("tieu_de") or node.get("slug") or _node_key(node))[:90]


class GraphQueryService:
    """Service querying Neo4j neighborhood graph structure (`depth <= 2`) directly without mock data."""

    def __init__(self, driver: Any | None = None, llm_router: Any | None = None) -> None:
        self.driver = driver
        self.llm_router = llm_router

    async def _enrich_nodes(self, nodes: list[dict[str, Any]], limit: int = 12) -> None:
        """Add validated semantic metadata without ever changing graph identity or topology."""
        if not self.llm_router:
            return
        for node in nodes[:limit]:
            try:
                prompt = json.dumps(
                    {
                        "instruction": "Chỉ bổ sung metadata ngữ nghĩa. Không tạo node/edge/citation/ID.",
                        "node_id": node["id"], "node_type": node["type"],
                        "content": node["label"],
                    },
                    ensure_ascii=False,
                )
                enrichment = await self.llm_router.complete(
                    task="graph_node_enrichment", prompt=prompt,
                    schema=GraphNodeEnrichment, complexity="low",
                )
                if not enrichment.get("needs_review"):
                    node["enrichment"] = enrichment
                    node["short_label"] = enrichment["short_label"]
            except Exception:  # noqa: BLE001 - graph must remain available when the model fails
                logger.warning("Graph enrichment unavailable", extra={"node_id": node["id"]}, exc_info=True)

    async def get_neighborhood(
        self,
        seed_id: str,
        depth: int = 1,
        limit: int = 200,
        min_importance: float = 0,
        include_types: list[str] | None = None,
        enrich: bool = False,
    ) -> dict[str, Any]:
        """Fetch real graph neighborhood (`depth <= 2`). Returns only actual nodes and relationships."""
        bounded_depth = max(1, min(depth, 2))
        bounded_limit = max(1, min(limit, 300))
        nodes_map: dict[str, dict[str, Any]] = {}
        edges_set: set[tuple[str, str, str]] = set()

        if self.driver and hasattr(self.driver, "session"):
            try:
                # Match a seed by any natural key: internal id, khoản/điều id, slug, OR the human
                # document number (so_hieu). Also match by prefix so typing just the số hiệu
                # ("01/2016/NQ-HDND") seeds the whole document tree (its Điều/Khoản), not only the
                # exact "01/2016/NQ-HDND::D1.K2".
                query = f"""
                MATCH path = (seed)-[r*1..{bounded_depth}]-(neighbor)
                WHERE seed.vb_id = $seed_id OR seed.khoan_id = $seed_id OR seed.dieu_id = $seed_id
                         OR seed.bai_dang_id = $seed_id OR seed.id = $seed_id
                         OR seed.so_hieu = $seed_id OR seed.so_hieu_norm = $seed_id OR seed.slug = $seed_id
                   OR seed.khoan_id STARTS WITH ($seed_id + '::')
                   OR seed.dieu_id STARTS WITH ($seed_id + '::')
                RETURN nodes(path) AS ns, relationships(path) AS rels
                LIMIT {bounded_limit}
                """
                async with self.driver.session() as session:
                    res = await session.run(query, seed_id=seed_id)
                    async for record in res:
                        for node in record["ns"]:
                            if node is None:
                                continue
                            nid = _node_key(node)
                            raw_type, node_type = _node_type(node)
                            label_str = _node_label(node, raw_type)
                            # Keep neighborhood payloads compact. Large canonical text stays in
                            # Neo4j and can be retrieved by QA/detail flows when needed.
                            raw_properties = dict(node)
                            properties = _jsonable({
                                key: value for key, value in raw_properties.items()
                                if key not in {"embedding", "vector", "noi_dung", "content", "raw_text"}
                            })
                            nodes_map[nid] = {
                                "id": nid, "type": node_type, "raw_type": raw_type,
                                "label": label_str, "short_label": label_str[:28] + ("…" if len(label_str) > 28 else ""),
                                "properties": properties,
                            }

                        for rel in record["rels"]:
                            if rel is None:
                                continue
                            start_node = rel.start_node
                            end_node = rel.end_node
                            sid = _node_key(start_node)
                            eid = _node_key(end_node)
                            rel_type = getattr(rel, "type", None) or type(rel).__name__
                            edges_set.add((sid, eid, rel_type))
            except Exception:
                logger.warning("Failed to explore neighborhood for seed %s", seed_id, exc_info=True)

        local_degree = {nid: 0 for nid in nodes_map}
        for source, target, _ in edges_set:
            if source in local_degree:
                local_degree[source] += 1
            if target in local_degree:
                local_degree[target] += 1

        for nid, node in nodes_map.items():
            props = node["properties"]
            connections = local_degree[nid]
            citations = int(props.get("citation_count") or props.get("trich_dan_count") or 0)
            access = int(props.get("access_frequency") or props.get("view_count") or 0)
            level = _LEGAL_LEVEL_SCORE.get(node["type"], 20)
            score = connections * 0.4 + citations * 0.3 + level * 0.2 + access * 0.1
            node.update({
                "connection_count": connections,
                "citation_count": citations,
                "legal_level_score": level,
                "access_frequency": access,
                "centrality": round(connections / max(1, len(nodes_map) - 1), 4),
                "importance_score": round(score, 2),
                "size": round(min(70, max(12, 12 + math.sqrt(max(0, score)) * 5)), 1),
            })

        allowed = {t.strip().lower() for t in include_types or [] if t.strip()}
        ranked = sorted(nodes_map.values(), key=lambda n: (-n["importance_score"], n["id"]))
        filtered = [n for n in ranked if n["importance_score"] >= min_importance and (not allowed or n["type"] in allowed)]
        selected = filtered[:bounded_limit]
        if enrich:
            await self._enrich_nodes(selected)
        selected_ids = {n["id"] for n in selected}
        edges_list = [
            {"source": s, "target": t, "type": r}
            for s, t, r in edges_set if s in selected_ids and t in selected_ids
        ]
        return {
            "seed_id": seed_id,
            "depth": bounded_depth,
            "nodes": selected,
            "edges": edges_list,
            "meta": {
                "total_nodes": len(nodes_map), "returned_nodes": len(selected),
                "truncated": len(filtered) > len(selected), "layout_hint": "force",
            },
        }

    async def seed_suggestions(self, limit: int = 20) -> dict[str, Any]:
        """Return useful starting nodes so the graph page is usable without memorized IDs."""
        bounded_limit = max(1, min(limit, 50))
        items: list[dict[str, Any]] = []
        if self.driver and hasattr(self.driver, "session"):
            try:
                query = """
                MATCH (n)
                WHERE n.vb_id IS NOT NULL OR n.khoan_id IS NOT NULL OR n.dieu_id IS NOT NULL OR n.bai_dang_id IS NOT NULL
                WITH n, labels(n) AS labels, size([(n)--() | 1]) AS degree
                  RETURN coalesce(n.vb_id, n.khoan_id, n.dieu_id, n.bai_dang_id, n.slug, n.id) AS id,
                      labels[0] AS type,
                      CASE
                        WHEN n:VanBanPhapLuat OR n:VanBan THEN coalesce(n.so_hieu, n.ten, n.vb_id)
                        WHEN n:Chuong THEN 'Chương ' + coalesce(toString(n.so), toString(n.so_chuong), n.id)
                        WHEN n:Dieu THEN 'Điều ' + coalesce(toString(n.so), toString(n.so_dieu), n.dieu_id)
                        WHEN n:Khoan THEN 'Khoản ' + coalesce(toString(n.so), toString(n.so_khoan), n.khoan_id)
                        ELSE coalesce(n.ten, n.tieu_de, n.slug, n.id)
                      END AS label,
                      degree
                ORDER BY degree DESC, type ASC
                LIMIT $limit
                """
                async with self.driver.session() as session:
                    res = await session.run(query, limit=bounded_limit)
                    async for r in res:
                        items.append(
                            {
                                "id": str(r.get("id")),
                                "type": r.get("type") or "Node",
                                "label": str(r.get("label") or r.get("id"))[:120],
                                "degree": int(r.get("degree") or 0),
                            }
                        )
            except Exception:
                logger.warning("Failed to fetch seed suggestions from Neo4j", exc_info=True)
        return {"items": items, "total": len(items)}

    async def clarity_index(self, min_volume: int = 5, limit: int = 50) -> dict[str, Any]:
        """Idea 02 — Legal Clarity Index.

        Aggregates the DOI_CHIEU edges (citizen opinions cross-checked against a Khoản) to find which
        provisions are most often misunderstood. High ``clarity_risk`` (share of mâu_thuẫn/khong_ro)
        weighted by ``log(volume + 1)`` ranks clauses that are both contested and widely discussed.
        This is a communication / clarity-risk signal — NOT Shannon entropy and NOT a legal judgement
        that the law itself is wrong.
        """
        bounded_min = max(1, min(min_volume, 1000))
        bounded_limit = max(1, min(limit, 200))
        items: list[dict[str, Any]] = []
        if self.driver and hasattr(self.driver, "session"):
            try:
                query = """
                MATCH (y:YKien)-[d:DOI_CHIEU]->(k:Khoan)
                WITH k,
                     count(CASE WHEN d.label = 'mau_thuan' THEN 1 END) AS mau_thuan,
                     count(CASE WHEN d.label = 'khong_ro'  THEN 1 END) AS khong_ro,
                     count(*) AS tong
                WHERE tong >= $min_volume
                RETURN k.khoan_id AS khoan_id, k.noi_dung AS noi_dung,
                       mau_thuan AS mau_thuan, khong_ro AS khong_ro, tong AS volume,
                       toFloat(mau_thuan + khong_ro) / tong AS clarity_risk
                ORDER BY clarity_risk * log(volume + 1) DESC
                LIMIT $limit
                """
                async with self.driver.session() as session:
                    res = await session.run(query, min_volume=bounded_min, limit=bounded_limit)
                    async for r in res:
                        items.append(
                            {
                                "khoan_id": r.get("khoan_id"),
                                "noi_dung": r.get("noi_dung"),
                                "mau_thuan": int(r.get("mau_thuan") or 0),
                                "khong_ro": int(r.get("khong_ro") or 0),
                                "volume": int(r.get("volume") or 0),
                                "clarity_risk": round(float(r.get("clarity_risk") or 0.0), 3),
                            }
                        )
            except Exception:
                logger.warning("Failed to fetch clarity index from Neo4j", exc_info=True)
        return {"min_volume": bounded_min, "items": items, "total": len(items)}
