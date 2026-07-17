from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends
from app.api.deps import get_db_pool, get_neo4j_driver, require_admin
from app.core.envelope import success_response
from app.core.logging import get_request_id
from app.services.dashboard_service import DashboardService

router = APIRouter(tags=["Admin Dashboard"], dependencies=[Depends(require_admin())])


@router.get("/dashboard/summary", summary="Dữ liệu tổng hợp theo thời gian thực cho Command Center widgets")
async def get_dashboard_summary(
    pool: Any = Depends(get_db_pool),
    driver: Any = Depends(get_neo4j_driver),
) -> dict[str, Any]:
    service = DashboardService(pool=pool, neo4j_driver=driver)
    res = await service.get_summary()
    return success_response(data=res, request_id=get_request_id())
