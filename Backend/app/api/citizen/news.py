from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.deps import get_db_pool, get_neo4j_driver
from app.core.envelope import success_response
from app.core.logging import get_request_id
from app.services.brief_service import BriefService

router = APIRouter(tags=["Citizen News"])


@router.get("/news", summary="Danh sách tin tức/bài tóm tắt pháp lý đã được xuất bản")
async def citizen_list_news(
    pool: Any = Depends(get_db_pool),
    driver: Any = Depends(get_neo4j_driver),
) -> dict[str, Any]:
    service = BriefService(pool=pool, neo4j_driver=driver)
    # Strictly enforce status=published for Citizen Portal
    items = await service.list_briefs(status="published")
    return success_response(data={"items": items, "total": len(items)}, request_id=get_request_id())


@router.get("/news/{id}", summary="Chi tiết bài tin tức/tóm tắt pháp lý đã xuất bản")
async def citizen_get_news(
    id: str,
    pool: Any = Depends(get_db_pool),
    driver: Any = Depends(get_neo4j_driver),
) -> dict[str, Any]:
    service = BriefService(pool=pool, neo4j_driver=driver)
    item = await service.get_brief(id)
    if not item or item.get("status") != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tin tức không tồn tại hoặc chưa được xuất bản chính thức ra Citizen Portal.",
        )
    return success_response(data=item, request_id=get_request_id())
