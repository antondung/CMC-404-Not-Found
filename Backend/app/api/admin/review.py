from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.api.deps import get_db_pool, get_neo4j_driver, require_admin, UserToken
from app.core.envelope import success_response
from app.core.logging import get_request_id

router = APIRouter(tags=["Admin Review"], dependencies=[Depends(require_admin())])


class ReviewActionRequest(BaseModel):
    action: str = Field(..., description="Hành động: approve, reject, override")
    override_data: dict[str, Any] | None = Field(default=None, description="Dữ liệu ghi đè nếu action là override")
    note: str | None = Field(default=None, description="Ghi chú nghiệp vụ")


@router.get("/review", summary="Danh sách hàng đợi cần duyệt (parse, extract, nli nhầm lẫn)")
async def list_review_queue(
    type: str | None = None,
    pool: Any = Depends(get_db_pool),
    driver: Any = Depends(get_neo4j_driver),
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    # Query Neo4j for nodes with needs_review = True
    if driver and hasattr(driver, "session"):
        try:
            query = "MATCH (n) WHERE n.needs_review = true RETURN id(n) AS id, labels(n) AS labels, n LIMIT 50"
            async with driver.session() as session:
                res = await session.run(query)
                async for record in res:
                    n = record["n"]
                    lbls = record["labels"]
                    items.append({
                        "id": str(n.get("bai_dang_id") or n.get("khoan_id") or record["id"]),
                        "type": "social_post" if "BaiDang" in lbls else ("legal_khoan" if "Khoan" in lbls else "entity"),
                        "source": str(lbls),
                        "content": n.get("noi_dung", ""),
                        "reason": n.get("review_reason", "Low confidence score during BE1/BE2 extraction"),
                        "created_at": n.get("ngay_dang", "2026-07-16T10:00:00Z"),
                    })
        except Exception:
            pass

    if type:
        items = [x for x in items if x.get("type") == type]

    return success_response(data={"items": items, "total": len(items)}, request_id=get_request_id())


@router.patch("/review/{id}", summary="Phê duyệt hoặc từ chối phần tử trong hàng đợi review")
async def process_review_item(
    id: str,
    request: ReviewActionRequest,
    driver: Any = Depends(get_neo4j_driver),
    user: UserToken = Depends(require_admin()),
) -> dict[str, Any]:
    if driver and hasattr(driver, "session"):
        try:
            query = "MATCH (n) WHERE n.bai_dang_id = $id OR n.khoan_id = $id OR id(n) = $id SET n.needs_review = false, n.reviewed_by = $user RETURN n"
            async with driver.session() as session:
                await session.run(query, id=id, user=user.user_id)
        except Exception:
            pass

    return success_response(
        data={
            "id": id,
            "action": request.action,
            "status": "processed",
            "reviewed_by": user.user_id,
            "note": request.note,
        },
        request_id=get_request_id(),
    )
