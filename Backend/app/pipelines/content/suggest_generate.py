from __future__ import annotations

from pydantic import BaseModel, Field
from app.intelligence.llm_router import LLMRouter
from app.pipelines.content.validators import validate_citations
from app.schemas import SuggestDraft

DEFAULT_DISCLAIMER = "Gợi ý nội bộ — cần kiểm chứng trước khi phát hành."


class SuggestGenerateInput(BaseModel):
    alert_ids: list[str] = Field(min_length=1)


class SuggestGenerateService:
    def __init__(self, legal_repo, content_repo, router: LLMRouter | None = None) -> None:
        self.legal_repo = legal_repo
        self.content_repo = content_repo
        self.router = router or LLMRouter()

    async def generate(self, data: SuggestGenerateInput) -> SuggestDraft:
        alerts = await self.content_repo.load_alerts(data.alert_ids)
        khoan_ids = sorted({kid for alert in alerts for kid in alert.get("khoan_ids", [])})
        sources = await self.legal_repo.get_khoan_many(khoan_ids) if khoan_ids else []
        if not sources:
            draft = SuggestDraft(draft_content="Chưa đủ căn cứ để đề xuất đính chính.", related_alert_ids=data.alert_ids, disclaimer=DEFAULT_DISCLAIMER, status="needs_review", audit={"reason": "missing_evidence"})
            await self.content_repo.save_suggestion(draft)
            return draft
        context = "\n".join(f"[{s.khoan_id}] {s.noi_dung}" for s in sources)
        prompt = f"retrieved_context:\n{context}\nAlerts: {alerts}\nSinh DeXuatDinhChinh draft, không kết luận cá nhân/bài đăng là tin giả, luôn thể hiện uncertainty nếu thiếu evidence. Disclaimer bắt buộc: {DEFAULT_DISCLAIMER}"
        raw = await self.router.complete("suggest", prompt, SuggestDraft, "high")
        draft = SuggestDraft.model_validate(raw)
        if not draft.disclaimer.strip():
            draft.disclaimer = DEFAULT_DISCLAIMER
        validate_citations(draft.citations, sources)
        await self.content_repo.save_suggestion(draft)
        return draft
