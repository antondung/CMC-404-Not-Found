from __future__ import annotations

from collections import Counter
import re
from typing import Any
from app.config import BE2Config, get_config
from app.schemas import NliLabel


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)


class AlertSignalService:
    def __init__(self, repository: Any, config: BE2Config | None = None) -> None:
        self.repository = repository
        self.config = config or get_config()

    async def maybe_create_alert(self, *, signals: list[dict[str, Any]], dry_run: bool = False) -> dict[str, Any] | None:
        eligible = [
            s for s in signals
            if self._has_provenance(s)
            and s.get("label") in {NliLabel.MAU_THUAN, NliLabel.MAU_THUAN.value}
            and float(s.get("score", 0.0)) >= self.config.nli_confidence_threshold
        ]
        unique: dict[str, dict[str, Any]] = {}
        for signal in eligible:
            content_hash = str(signal.get("content_hash") or "").strip()
            identity = "|".join((
                content_hash.lower(),
                str(signal.get("misconception_id") or ""),
                str(signal.get("khoan_id") or ""),
                str(signal.get("claim_text") or ""),
            ))
            unique.setdefault(identity, signal)
        eligible = list(unique.values())
        if len(eligible) < self.config.alert_volume_threshold or dry_run:
            return None
        keys = [
            (s.get("misconception_id"), s.get("chu_de"), s.get("khoan_id"))
            for s in eligible
        ]
        (misconception_id, chu_de, khoan_id), volume = Counter(keys).most_common(1)[0]
        if volume < self.config.alert_volume_threshold:
            return None
        dedupe_key = (
            f"misconception:{misconception_id}"
            if misconception_id
            else f"{chu_de}:{khoan_id}"
        )
        if await self.repository.find_recent_alert(dedupe_key, self.config.alert_cooldown_s):
            return None
        grouped_signals = [
            s
            for s in eligible
            if (s.get("misconception_id"), s.get("chu_de"), s.get("khoan_id"))
            == (misconception_id, chu_de, khoan_id)
        ]
        risk_score = max(
            (float(item["risk_score"]) for item in grouped_signals if item.get("risk_score") is not None),
            default=None,
        )
        risk_factors = next(
            (item.get("risk_factors") for item in grouped_signals if item.get("risk_factors")),
            [],
        )
        alert = {
            "chu_de": chu_de,
            "khoan_ids": [khoan_id],
            "misconception_ids": [misconception_id] if misconception_id else [],
            "severity": self._risk_severity(risk_score) if risk_score is not None else self._severity(volume),
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "volume": volume,
            "status": "open",
            "dedupe_key": dedupe_key,
            "signals": grouped_signals,
            "provenance_status": "complete",
            "note": "Tín hiệu cần xem xét, không phải kết luận nội dung giả.",
        }
        alert_id = await self.repository.save_alert(alert)
        return {"alert_id": alert_id, **alert}

    @staticmethod
    def _has_provenance(signal: dict[str, Any]) -> bool:
        required = (
            "bai_dang_id",
            "ykien_id",
            "claim_text",
            "evidence_span",
            "post_url",
            "khoan_id",
            "content_hash",
        )
        if not all(isinstance(signal.get(key), str) and signal[key].strip() for key in required):
            return False
        if _SHA256_RE.fullmatch(str(signal["content_hash"]).strip()) is None:
            return False
        post_content = signal.get("post_content")
        return isinstance(post_content, str) and signal["evidence_span"] in post_content

    def _severity(self, volume: int) -> str:
        if volume >= self.config.alert_volume_threshold * 3:
            return "high"
        if volume >= self.config.alert_volume_threshold * 2:
            return "medium"
        return "low"

    @staticmethod
    def _risk_severity(risk_score: float) -> str:
        if risk_score >= 0.85:
            return "critical"
        if risk_score >= 0.70:
            return "high"
        if risk_score >= 0.50:
            return "medium"
        return "low"
