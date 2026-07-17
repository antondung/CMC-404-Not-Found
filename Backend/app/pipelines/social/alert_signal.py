from __future__ import annotations

from collections import Counter
from typing import Any
from app.config import BE2Config, get_config
from app.schemas import NliLabel


class AlertSignalService:
    def __init__(self, repository: Any, config: BE2Config | None = None) -> None:
        self.repository = repository
        self.config = config or get_config()

    async def maybe_create_alert(self, *, signals: list[dict[str, Any]], dry_run: bool = False) -> dict[str, Any] | None:
        eligible = [s for s in signals if s.get("label") == NliLabel.MAU_THUAN and float(s.get("score", 0.0)) >= self.config.nli_confidence_threshold]
        if len(eligible) < self.config.alert_volume_threshold or dry_run:
            return None
        keys = [(s.get("chu_de"), s.get("khoan_id")) for s in eligible]
        (chu_de, khoan_id), volume = Counter(keys).most_common(1)[0]
        if volume < self.config.alert_volume_threshold:
            return None
        dedupe_key = f"{chu_de}:{khoan_id}"
        if await self.repository.find_recent_alert(dedupe_key, self.config.alert_cooldown_s):
            return None
        alert = {"chu_de": chu_de, "khoan_ids": [khoan_id], "severity": self._severity(volume), "volume": volume, "status": "open", "dedupe_key": dedupe_key, "note": "Tín hiệu cần xem xét, không phải kết luận nội dung giả."}
        alert_id = await self.repository.save_alert(alert)
        return {"alert_id": alert_id, **alert}

    def _severity(self, volume: int) -> str:
        if volume >= self.config.alert_volume_threshold * 3:
            return "high"
        if volume >= self.config.alert_volume_threshold * 2:
            return "medium"
        return "low"
