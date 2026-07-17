"""Legal NER/RE extractor: extract structured legal entities from a Khoản's text.

Calls the LLMRouter (BE2 intelligence) with task="ner_re_complex" and validates the
response against KhoanEntities schema.  Falls back gracefully when the LLM is
unavailable so that the ingest pipeline is not blocked.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Template prompt injected with the Pydantic schema so the LLM knows exactly
# what JSON structure to return.
_NER_PROMPT_TEMPLATE = """\
Bạn là chuyên gia pháp lý. Hãy đọc đoạn Khoản sau và trích xuất các thực thể pháp lý.
Trả về JSON hợp lệ theo schema sau (KHÔNG thêm bất kỳ text nào ngoài JSON):

SCHEMA:
{schema}

KHOẢN [{khoan_id}]:
{khoan_text}
"""


class LegalExtractor:
    """Trích xuất các thực thể pháp lý (NER/RE) từ nội dung của từng Khoản
    bằng cách gọi LLM qua LLMRouter (schema-locked output).

    Args:
        llm_router: Instance of ``LLMRouter`` (injected from worker context or API deps).
                    If None, extractor returns an empty-entity result (best-effort fallback).
    """

    def __init__(self, llm_router: Any = None) -> None:
        from domain.legal_schemas import KhoanEntities  # local import avoids circular deps

        self._schema = KhoanEntities
        self._schema_json = json.dumps(KhoanEntities.model_json_schema(), ensure_ascii=False, indent=2)
        self.llm_router = llm_router

    async def extract_entities_from_khoan(self, khoan_id: str, khoan_text: str) -> dict[str, Any]:
        """Call LLM to extract legal entities from a single Khoản's text.

        Returns a dict matching ``KhoanEntities`` schema on success, or
        ``{"error": "...", "khoan_id": khoan_id}`` on failure.
        """
        if not khoan_text or not khoan_text.strip():
            return self._empty(khoan_id, reason="empty_text")

        if self.llm_router is None:
            logger.warning("legal_extractor: no LLM router available for khoan %s; skipping NER", khoan_id)
            return self._empty(khoan_id, reason="no_llm_router")

        prompt = _NER_PROMPT_TEMPLATE.format(
            schema=self._schema_json,
            khoan_id=khoan_id,
            khoan_text=khoan_text.strip(),
        )

        logger.info("legal_extractor: NER call for khoan %s (%d chars)", khoan_id, len(khoan_text))
        try:
            result = await self.llm_router.complete(
                task="ner_re_complex",
                prompt=prompt,
                schema=self._schema,
                complexity="high",
            )
            # If LLM returned a needs_review signal, propagate it.
            if result.get("needs_review"):
                logger.warning("legal_extractor: LLM needs_review for khoan %s", khoan_id)
                return {**self._empty(khoan_id, reason="llm_needs_review"), "needs_review": True}
            return result
        except Exception as exc:  # noqa: BLE001 — NER is best-effort; never block ingest
            logger.warning("legal_extractor: LLM call failed for khoan %s: %s", khoan_id, exc)
            return self._empty(khoan_id, reason=str(exc))

    @staticmethod
    def _empty(khoan_id: str, *, reason: str = "") -> dict[str, Any]:
        """Return an empty but schema-valid entity dict."""
        return {
            "chu_the": [],
            "nghia_vu": [],
            "quyen_loi": [],
            "hanh_vi_cam": [],
            "thoi_han": [],
            "che_tai": [],
            "_khoan_id": khoan_id,
            "_skip_reason": reason,
        }
