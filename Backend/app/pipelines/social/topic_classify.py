from __future__ import annotations

from typing import Any
from app.config import BE2Config, get_config
from app.intelligence.embedder import Embedder
from app.schemas import TopicResult


class TopicClassifier:
    def __init__(self, vector_client: Any, embedder: Embedder | None = None, config: BE2Config | None = None) -> None:
        self.vector_client = vector_client
        self.embedder = embedder or Embedder(config)
        self.config = config or get_config()

    async def classify(self, *, bai_dang_id: str, content: str, limit: int = 5) -> TopicResult:
        vector = (await self.embedder.embed_texts([content]))[0]
        hits = await self.vector_client.search("chude", vector, limit=limit, query_filter=None)
        if not hits:
            return TopicResult(bai_dang_id=bai_dang_id, score=0.0, status="unknown", model=self.config.embedding_model)
        best = max(hits, key=lambda h: float(h.get("score", 0.0)))
        score = float(best.get("score", 0.0))
        slug = best.get("payload", {}).get("slug") or best.get("slug")
        status = "classified" if slug and score >= self.config.topic_threshold else "needs_review"
        return TopicResult(bai_dang_id=bai_dang_id, slug=slug, score=score, status=status, model=self.config.embedding_model)
