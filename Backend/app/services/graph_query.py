from __future__ import annotations

from typing import Any


class GraphQueryService:
    """Service querying Neo4j neighborhood graph structure (`depth <= 2`) directly without mock data."""

    def __init__(self, driver: Any | None = None) -> None:
        self.driver = driver

    async def get_neighborhood(self, seed_id: str, depth: int = 1) -> dict[str, Any]:
        """Fetch real graph neighborhood (`depth <= 2`). Returns only actual nodes and relationships."""
        bounded_depth = max(1, min(depth, 2))
        nodes_map: dict[str, dict[str, Any]] = {}
        edges_set: set[tuple[str, str, str]] = set()

        if self.driver and hasattr(self.driver, "session"):
            try:
                query = f"""
                MATCH path = (seed)-[r*1..{bounded_depth}]-(neighbor)
                WHERE seed.vb_id = $seed_id OR seed.khoan_id = $seed_id OR seed.slug = $seed_id OR id(seed) = $seed_id
                RETURN nodes(path) AS ns, relationships(path) AS rels
                LIMIT 200
                """
                async with self.driver.session() as session:
                    res = await session.run(query, seed_id=seed_id)
                    async for record in res:
                        for node in record["ns"]:
                            if node is None:
                                continue
                            nid = str(node.get("vb_id") or node.get("khoan_id") or node.get("slug") or node.get("id") or id(node))
                            labels = list(node.labels) if hasattr(node, "labels") else ["Node"]
                            node_type = labels[0] if labels else "Node"
                            label_str = str(node.get("so_hieu") or node.get("tieu_de") or node.get("noi_dung") or node.get("ten") or nid)[:60]
                            nodes_map[nid] = {"id": nid, "type": node_type, "label": label_str, "properties": dict(node)}

                        for rel in record["rels"]:
                            if rel is None:
                                continue
                            start_node = rel.start_node
                            end_node = rel.end_node
                            sid = str(start_node.get("vb_id") or start_node.get("khoan_id") or start_node.get("slug") or id(start_node))
                            eid = str(end_node.get("vb_id") or end_node.get("khoan_id") or end_node.get("slug") or id(end_node))
                            rel_type = type(rel).__name__ if hasattr(rel, "__class__") else "REL"
                            edges_set.add((sid, eid, rel_type))
            except Exception:
                pass

        edges_list = [{"source": s, "target": t, "type": r} for s, t, r in edges_set]
        return {
            "seed_id": seed_id,
            "depth": bounded_depth,
            "nodes": list(nodes_map.values()),
            "edges": edges_list,
        }
