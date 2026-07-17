from __future__ import annotations

from pydantic import BaseModel, Field
from app.exceptions import ValidationError
from app.intelligence.llm_router import LLMRouter


class RerankItem(BaseModel):
    khoan_id: str
    score: float = Field(ge=0, le=1)
    reason: str | None = None


class RerankOutput(BaseModel):
    items: list[RerankItem]


class Reranker:
    def __init__(self, router: LLMRouter | None = None) -> None:
        self.router = router or LLMRouter()

    async def rerank(self, query: str, candidates: list) -> list:
        if not query.strip() or not candidates:
            raise ValidationError("query and candidates are required")
        ids = {c.get("khoan_id") if isinstance(c, dict) else getattr(c, "khoan_id", None) for c in candidates}
        prompt = "retrieved_context:\n" + "\n".join(str(c) for c in candidates) + f"\nQuery: {query}\nReturn items with khoan_id and score."
        result = await self.router.complete("rerank", prompt, RerankOutput, "high")
        if result.get("needs_review"):
            return []
        items = result.get("items", [])
        invalid = [item for item in items if item.get("khoan_id") not in ids]
        if invalid:
            raise ValidationError("rerank returned unknown candidate id", details={"invalid": invalid})
        return sorted(items, key=lambda item: item["score"], reverse=True)


_default_reranker: Reranker | None = None


async def rerank(query: str, candidates: list) -> list:
    global _default_reranker
    if _default_reranker is None:
        _default_reranker = Reranker()
    return await _default_reranker.rerank(query, candidates)
