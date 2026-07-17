from __future__ import annotations

import json
from typing import Any
from app.schemas import BriefDraft, SuggestDraft


class PostgresContentRepository:
    """Async SQL adapter for BE2 draft metadata. Uses existing tables from Data/SYSTEM_DATA.md."""

    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def save_brief(self, draft: BriefDraft) -> str:
        query = """
        INSERT INTO briefs (title, status, payload_json)
        VALUES ($1, $2, $3)
        ON CONFLICT DO NOTHING
        RETURNING id
        """
        payload = json.dumps(draft.model_dump(mode="json"), ensure_ascii=False)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, draft.title, draft.status.value, payload)
        return str(row["id"]) if row else ""

    async def save_suggestion(self, draft: SuggestDraft) -> str:
        query = """
        INSERT INTO suggestions (status, payload_json)
        VALUES ($1, $2)
        RETURNING id
        """
        payload = json.dumps(draft.model_dump(mode="json"), ensure_ascii=False)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, draft.status.value, payload)
        return str(row["id"])

    async def load_alerts(self, alert_ids: list[str]) -> list[dict[str, Any]]:
        query = "SELECT id, payload_json FROM alerts WHERE id = ANY($1::uuid[])"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, alert_ids)
        alerts: list[dict[str, Any]] = []
        for row in rows:
            payload = row["payload_json"] or {}
            if isinstance(payload, str):
                payload = json.loads(payload)
            payload.setdefault("alert_id", str(row["id"]))
            alerts.append(payload)
        return alerts
