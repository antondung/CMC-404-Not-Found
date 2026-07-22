from __future__ import annotations

from typing import Any

from app.core.logging import get_logger


logger = get_logger("app.workers.amendment_reconciliation")


async def amendment_reconciliation_monitor(ctx: dict[str, Any]) -> dict[str, Any]:
    """Run a read-only reconciliation scan and surface degraded state to operations."""
    service = ctx.get("amendment_reconciliation_service")
    config = ctx["config"]
    if service is None:
        logger.error("amendment_reconciliation_monitor_unavailable")
        return {"status": "unavailable", "issue_count": 0}
    report = await service.check(limit=config.amendment_reconciliation_monitor_limit)
    payload = report.model_dump(mode="json")
    if report.status == "degraded":
        logger.error(
            "amendment_reconciliation_degraded issue_count=%s issues=%s",
            report.issue_count,
            [item.model_dump(mode="json") for item in report.issues],
        )
    else:
        logger.info(
            "amendment_reconciliation_healthy scanned_graph_commits=%s",
            report.scanned_graph_commits,
        )
    return payload


__all__ = ["amendment_reconciliation_monitor"]
