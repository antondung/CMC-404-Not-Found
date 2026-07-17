from __future__ import annotations

from typing import Any
from app.config import BE2Config, get_config
from app.exceptions import ValidationError
from app.intelligence.embedder import Embedder
from app.intelligence.rerank import Reranker
from app.schemas import LinkCandidate, LinkPreview, TopicResult


class EntityLinker:
    def __init__(self, vector_client: Any, social_repo: Any, embedder: Embedder | None = None, reranker: Reranker | None = None, config: BE2Config | None = None) -> None:
        self.vector_client = vector_client
        self.social_repo = social_repo
        self.embedder = embedder or Embedder(config)
        self.reranker = reranker or Reranker()
        self.config = config or get_config()

    async def preview(self, *, bai_dang_id: str, content: str, topic: TopicResult, top_k: int = 10, dry_run: bool = True) -> LinkPreview:
        reasons: list[str] = []
        if topic.status != "classified" or not topic.slug:
            return LinkPreview(bai_dang_id=bai_dang_id, candidates=[], proposed_edges=[], dry_run=dry_run, status="blocked", reasons=["missing_valid_topic"])
        if topic.score < self.config.topic_threshold:
            return LinkPreview(bai_dang_id=bai_dang_id, candidates=[], proposed_edges=[], dry_run=dry_run, status="blocked", reasons=["topic_score_below_threshold"])
        vector = (await self.embedder.embed_texts([content]))[0]
        hits = await self.vector_client.search("khoan", vector, limit=top_k, query_filter={"must": [{"key": "chu_de", "match": {"value": topic.slug}}]})
        candidates = [{"khoan_id": h.get("payload", {}).get("khoan_id"), "score": float(h.get("score", 0.0)), "payload": h.get("payload", {})} for h in hits]
        candidates = [c for c in candidates if c["khoan_id"]]
        ranked = await self.reranker.rerank(content, candidates) if candidates else []
        known_ids = {c["khoan_id"] for c in candidates}
        proposed: list[LinkCandidate] = []
        for item in ranked:
            if item["khoan_id"] not in known_ids:
                raise ValidationError("rerank returned unknown candidate id")
            if float(item["score"]) >= self.config.link_threshold:
                proposed.append(LinkCandidate(khoan_id=item["khoan_id"], score=float(item["score"]), reason=item.get("reason")))
        if not proposed:
            reasons.append("link_score_below_threshold")
        if not dry_run:
            for edge in proposed:
                await self.social_repo.create_link_edge(bai_dang_id, edge, method="vector_llm_rerank")
        return LinkPreview(bai_dang_id=bai_dang_id, candidates=[LinkCandidate(khoan_id=c["khoan_id"], score=c["score"]) for c in candidates], proposed_edges=proposed, dry_run=dry_run, status="ok" if proposed else "needs_review", reasons=reasons)
