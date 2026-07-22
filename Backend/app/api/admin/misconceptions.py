from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import (
    Role,
    UserToken,
    get_neo4j_repo,
    get_nli_service,
    get_temporal_law_service,
    require_admin,
    require_roles,
)
from app.config import BE2Config, get_config
from app.core.envelope import success_response
from app.core.logging import get_request_id
from app.services.temporal_misconception_service import TemporalMisconceptionService


router = APIRouter(
    tags=["Admin Misconceptions"],
    dependencies=[Depends(require_admin())],
)


class EvaluateMisconceptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_as_of: date = Field(default_factory=date.today)
    dry_run: bool = False


def _require_misconception_cluster(config: BE2Config) -> None:
    if not config.misconception_cluster_v2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Misconception cluster API is disabled",
        )


def _require_temporal_misconception(config: BE2Config) -> None:
    _require_misconception_cluster(config)
    if not all((
        config.legal_provision_v2_read,
        config.temporal_law_v2,
        config.misconception_temporal_v2,
    )):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Temporal misconception evaluation API is disabled",
        )


@router.get("/misconceptions", summary="List grounded misconception clusters")
async def list_misconceptions(
    status_filter: Literal["open", "reviewing", "corrected", "resolved"] | None = Query(
        default=None,
        alias="status",
    ),
    temporal_verdict: Literal[
        "SUPPORTED",
        "CONTRADICTED",
        "PARTIALLY_INCORRECT",
        "OUTDATED_BUT_PREVIOUSLY_TRUE",
        "UNVERIFIABLE",
        "NEEDS_REVIEW",
    ] | None = None,
    risk_severity: Literal["low", "medium", "high", "critical"] | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    config: BE2Config = Depends(get_config),
    repository: Any = Depends(get_neo4j_repo),
) -> dict[str, Any]:
    _require_misconception_cluster(config)
    items = await repository.list_misconceptions(
        status=status_filter,
        temporal_verdict=temporal_verdict,
        risk_severity=risk_severity,
        limit=limit,
        offset=offset,
    )
    return success_response(
        data={"items": items, "count": len(items), "limit": limit, "offset": offset},
        request_id=get_request_id(),
    )


@router.get("/misconceptions/{misconception_id}", summary="Get cluster provenance and claims")
async def get_misconception(
    misconception_id: UUID,
    config: BE2Config = Depends(get_config),
    repository: Any = Depends(get_neo4j_repo),
) -> dict[str, Any]:
    _require_misconception_cluster(config)
    item = await repository.get_misconception(str(misconception_id))
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Misconception cluster not found",
        )
    return success_response(data=item, request_id=get_request_id())


@router.post(
    "/misconceptions/{misconception_id}/evaluate",
    summary="Evaluate a misconception against publication-time and current law",
)
async def evaluate_misconception(
    misconception_id: UUID,
    request: EvaluateMisconceptionRequest,
    config: BE2Config = Depends(get_config),
    repository: Any = Depends(get_neo4j_repo),
    temporal_service: Any = Depends(get_temporal_law_service),
    nli_service: Any = Depends(get_nli_service),
    user: UserToken = Depends(require_roles(Role.ADMIN_PHAP_CHE)),
) -> dict[str, Any]:
    _require_temporal_misconception(config)
    report = await TemporalMisconceptionService(
        repository,
        temporal_service,
        nli_service,
        config,
    ).evaluate_cluster(
        str(misconception_id),
        current_as_of=request.current_as_of,
        actor_id=user.user_id,
        dry_run=request.dry_run,
    )
    return success_response(
        data=report.model_dump(mode="json"),
        request_id=get_request_id(),
    )


__all__ = ["router"]
