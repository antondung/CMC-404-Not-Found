from __future__ import annotations

import asyncio
from typing import Any
from app.config import BE2Config, get_config
from app.exceptions import ValidationError
from app.schemas import NliLabel, NliResult

LABEL_MAP = {
    "entailment": NliLabel.KHOP,
    "khop": NliLabel.KHOP,
    "contradiction": NliLabel.MAU_THUAN,
    "mau_thuan": NliLabel.MAU_THUAN,
    "neutral": NliLabel.KHONG_RO,
    "khong_ro": NliLabel.KHONG_RO,
}


class NLIService:
    def __init__(self, config: BE2Config | None = None, model: Any | None = None, model_name: str = "mdeberta-nli") -> None:
        self.config = config or get_config()
        self.model = model
        self.model_name = model_name

    async def nli_pair(self, premise: str, hypothesis: str) -> dict:
        if not premise.strip() or not hypothesis.strip():
            raise ValidationError("premise and hypothesis are required")
        try:
            raw = await asyncio.to_thread(self._predict, premise, hypothesis)
            result = self._normalize(raw)
        except Exception:
            result = NliResult(label=NliLabel.KHONG_RO, score=0.0, model=self.model_name, needs_review=True)
        if result.score < self.config.nli_confidence_threshold and result.label == NliLabel.MAU_THUAN:
            result = NliResult(label=NliLabel.KHONG_RO, score=result.score, model=result.model, needs_review=True)
        return result.model_dump()

    def _predict(self, premise: str, hypothesis: str) -> dict[str, Any]:
        if self.model is None:
            return {"label": "neutral", "score": 0.0, "model": self.model_name, "needs_review": True}
        return self.model.predict(premise=premise, hypothesis=hypothesis)

    def _normalize(self, raw: dict[str, Any]) -> NliResult:
        label_raw = str(raw.get("label", "")).lower()
        label = LABEL_MAP.get(label_raw, NliLabel.KHONG_RO)
        needs_review = bool(raw.get("needs_review", False)) or label_raw not in LABEL_MAP
        score = float(raw.get("score", 0.0))
        score = min(1.0, max(0.0, score))
        return NliResult(label=label, score=score, model=str(raw.get("model", self.model_name)), needs_review=needs_review)


_default_nli: NLIService | None = None


async def nli_pair(premise: str, hypothesis: str) -> dict:
    global _default_nli
    if _default_nli is None:
        _default_nli = NLIService()
    return await _default_nli.nli_pair(premise, hypothesis)
