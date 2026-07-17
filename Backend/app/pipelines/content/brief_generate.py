from __future__ import annotations

from pydantic import BaseModel
from app.intelligence.llm_router import LLMRouter
from app.pipelines.content.validators import validate_citations
from app.schemas import BriefDraft


class BriefGenerateInput(BaseModel):
    van_ban_id: str | None = None
    khoan_ids: list[str] | None = None
    diff_id: str | None = None


class BriefGenerateService:
    def __init__(self, legal_repo, content_repo, router: LLMRouter | None = None) -> None:
        self.legal_repo = legal_repo
        self.content_repo = content_repo
        self.router = router or LLMRouter()

    async def generate(self, data: BriefGenerateInput) -> BriefDraft:
        sources = []
        if data.khoan_ids:
            sources = await self.legal_repo.get_khoan_many(data.khoan_ids)
        elif data.van_ban_id:
            sources = await self.legal_repo.list_khoan_for_van_ban(data.van_ban_id)
        if not sources:
            return BriefDraft(title="Cần rà soát", bullets=["Chưa đủ căn cứ để sinh tóm tắt."], citations=[], status="needs_review", model="none", audit={"reason": "missing_sources"})
        context = "\n".join(f"[{s.khoan_id}] {s.noi_dung}" for s in sources)
        prompt = f"retrieved_context:\n{context}\nSinh BaiTomTat draft: title, bullets dễ hiểu, citations quote substring từ Khoản."
        raw = await self.router.complete("brief", prompt, BriefDraft, "high")
        draft = BriefDraft.model_validate(raw)
        validate_citations(draft.citations, sources)
        await self.content_repo.save_brief(draft)
        return draft
