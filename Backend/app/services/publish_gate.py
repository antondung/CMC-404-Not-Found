from __future__ import annotations

import json
import uuid
from typing import Any
from datetime import datetime, timezone
from app.core.security import Role, UserToken
from app.services.citation_validator import CitationValidator


class PublishGateService:
    """Guardrail service (Module 9a/9b) verifying briefs before publishing to Citizen Portal."""

    def __init__(self, pool: Any | None = None, neo4j_driver: Any | None = None) -> None:
        self.pool = pool
        self.driver = neo4j_driver
        self.validator = CitationValidator(neo4j_driver)

    async def verify_and_publish_brief(
        self,
        brief_id: str,
        actor: UserToken,
        brief_data: dict[str, Any],
    ) -> tuple[bool, dict[str, Any], list[str]]:
        """Verify actor roles, check citation accuracy against Neo4j, update status and record audit trail."""
        errors: list[str] = []

        # 1. Check actor roles
        if not actor.has_any_role([Role.ADMIN_TRUYEN_THONG, Role.ADMIN_OPS]):
            errors.append("Quyền hạn không đủ: Chỉ tài khoản có role admin_truyen_thong hoặc admin_ops mới được phép xuất bản Brief.")
            return False, {}, errors

        # 2. Check current status
        current_status = brief_data.get("status", "draft")
        if current_status == "published":
            return True, brief_data, ["Brief đã được xuất bản trước đó."]

        # 3. Citation validation check (must have at least one exact matching quote)
        citations = brief_data.get("citations", [])
        if not citations:
            errors.append("Từ chối xuất bản: Brief chưa có bất kỳ trích dẫn (citation) pháp lý nào làm căn cứ.")
            return False, {}, errors

        is_valid, validated_citations, val_errors = await self.validator.validate_quotes(citations)
        if not is_valid:
            errors.append("Từ chối xuất bản: Trích dẫn sai lệch nguyên văn hoặc bịa đặt (Hallucinated quote).")
            errors.extend(val_errors)
            return False, {}, errors

        # 4. Perform Publish Transition & Audit Log record
        now_str = datetime.now(timezone.utc).isoformat()
        audit_id = f"audit-{uuid.uuid4().hex[:8]}"

        if self.pool and hasattr(self.pool, "acquire"):
            try:
                async with self.pool.acquire() as conn:
                    # Update briefs table
                    await conn.execute(
                        "UPDATE briefs SET status = 'published', published_at = $1, published_by = $2 WHERE id = $3",
                        datetime.now(timezone.utc),
                        actor.user_id,
                        brief_id,
                    )
                    # Insert audit log
                    await conn.execute(
                        """
                        INSERT INTO audit_log (id, action, resource_id, actor_id, details_json, created_at)
                        VALUES ($1, 'publish_brief', $2, $3, $4, $5)
                        ON CONFLICT DO NOTHING
                        """,
                        audit_id,
                        brief_id,
                        actor.user_id,
                        json.dumps({"citations_count": len(validated_citations), "status": "published"}),
                        datetime.now(timezone.utc),
                    )
            except Exception:
                pass

        updated_brief = dict(brief_data)
        updated_brief["status"] = "published"
        updated_brief["published_at"] = now_str
        updated_brief["published_by"] = actor.user_id
        updated_brief["citations"] = validated_citations
        updated_brief["audit_id"] = audit_id

        return True, updated_brief, []
