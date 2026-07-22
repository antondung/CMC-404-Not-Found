from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import (
    Role,
    UserToken,
    get_amendment_commit_repository,
    get_amendment_review_repository,
    get_temporal_law_service,
    require_admin,
    require_roles,
)
from app.config import BE2Config, get_config
from app.core.envelope import success_response
from app.core.logging import get_request_id
from app.domain.amendment import LegalChangeType
from app.domain.amendment_review import (
    AmendmentBatchStatus,
    AmendmentCandidateDecision,
)
from app.services.amendment_preview_service import AmendmentPreviewService
from app.services.amendment_commit_service import AmendmentCommitService
from app.services.amendment_review_service import AmendmentReviewService
from app.services.amendment_reconciliation_service import AmendmentReconciliationService
from app.services.temporal_law_service import TemporalLawService


router = APIRouter(
    tags=["Admin Legal Amendments"],
    dependencies=[Depends(require_admin())],
)


class AmendmentPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    amendment_text: str = Field(min_length=5, max_length=50_000)
    old_provision_ids: list[str] = Field(min_length=1, max_length=100)
    new_provision_ids: list[str] = Field(min_length=1, max_length=100)
    target_logical_vb_id: str | None = Field(default=None, min_length=1)


class AmendmentReviewCreateRequest(AmendmentPreviewRequest):
    idempotency_key: str = Field(min_length=8, max_length=200)


class AmendmentCandidateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_revision: int = Field(ge=1)
    old_provision_id: str | None = Field(default=None, min_length=1)
    new_provision_id: str | None = Field(default=None, min_length=1)
    change_type: LegalChangeType | None = None
    proposed_effective_from: date | None = None
    decision: AmendmentCandidateDecision | None = None
    reviewer_note: str | None = Field(default=None, max_length=4_000)


class AmendmentTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class AmendmentDecisionRequest(AmendmentTransitionRequest):
    action: str = Field(pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=4_000)


class AmendmentCommitRequest(AmendmentTransitionRequest):
    idempotency_key: str = Field(min_length=8, max_length=200)
    amending_source_vb_id: str | None = Field(default=None, min_length=1)


def _require_amendment_preview(config: BE2Config) -> None:
    if not (config.legal_provision_v2_read and config.amendment_preview_v2):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amendment preview API is disabled",
        )


def _require_amendment_review(config: BE2Config) -> None:
    if not (
        config.legal_provision_v2_read
        and config.amendment_preview_v2
        and config.amendment_review_v2
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amendment review API is disabled",
        )


def _require_amendment_commit(config: BE2Config) -> None:
    _require_amendment_review(config)
    if not config.amendment_commit_v2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amendment commit API is disabled",
        )


@router.post("/legal/amendments/preview", summary="Preview amendment pairing without graph mutation")
async def preview_legal_amendment(
    request: AmendmentPreviewRequest,
    config: BE2Config = Depends(get_config),
    temporal_service: TemporalLawService = Depends(get_temporal_law_service),
) -> dict[str, Any]:
    _require_amendment_preview(config)
    service = AmendmentPreviewService(temporal_service)
    result = await service.preview(
        amendment_text=request.amendment_text,
        old_provision_ids=request.old_provision_ids,
        new_provision_ids=request.new_provision_ids,
        target_logical_vb_id=request.target_logical_vb_id,
    )
    return success_response(
        data=result.model_dump(mode="json"),
        request_id=get_request_id(),
    )


def _review_service(repository: Any, temporal_service: TemporalLawService) -> AmendmentReviewService:
    return AmendmentReviewService(repository, temporal_service)


@router.get(
    "/legal/amendment-reconciliation/health",
    summary="Inspect Neo4j to PostgreSQL amendment commit reconciliation",
)
async def get_amendment_reconciliation_health(
    limit: int = Query(default=200, ge=1, le=500),
    config: BE2Config = Depends(get_config),
    review_repository: Any = Depends(get_amendment_review_repository),
    graph_repository: Any = Depends(get_amendment_commit_repository),
    _: UserToken = Depends(require_roles(Role.ADMIN_PHAP_CHE)),
) -> dict[str, Any]:
    _require_amendment_review(config)
    report = await AmendmentReconciliationService(
        review_repository,
        graph_repository,
    ).check(limit=limit)
    return success_response(
        data=report.model_dump(mode="json"),
        request_id=get_request_id(),
    )


@router.post(
    "/legal/amendment-reviews",
    status_code=status.HTTP_201_CREATED,
    summary="Persist a canonical amendment preview for legal review",
)
async def create_amendment_review(
    request: AmendmentReviewCreateRequest,
    response: Response,
    config: BE2Config = Depends(get_config),
    repository: Any = Depends(get_amendment_review_repository),
    temporal_service: TemporalLawService = Depends(get_temporal_law_service),
    user: UserToken = Depends(require_roles(Role.ADMIN_PHAP_CHE)),
) -> dict[str, Any]:
    _require_amendment_review(config)
    batch, created = await _review_service(repository, temporal_service).create_review(
        amendment_text=request.amendment_text,
        old_provision_ids=request.old_provision_ids,
        new_provision_ids=request.new_provision_ids,
        target_logical_vb_id=request.target_logical_vb_id,
        idempotency_key=request.idempotency_key,
        actor_id=user.user_id,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return success_response(
        data={"created": created, "batch": batch.model_dump(mode="json")},
        request_id=get_request_id(),
    )


@router.get(
    "/legal/amendment-reviews",
    summary="List amendment review batches",
)
async def list_amendment_reviews(
    status_filter: AmendmentBatchStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    config: BE2Config = Depends(get_config),
    repository: Any = Depends(get_amendment_review_repository),
    temporal_service: TemporalLawService = Depends(get_temporal_law_service),
    _: UserToken = Depends(require_roles(Role.ADMIN_PHAP_CHE)),
) -> dict[str, Any]:
    _require_amendment_review(config)
    items, total = await _review_service(repository, temporal_service).list_reviews(
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return success_response(
        data={
            "items": [item.model_dump(mode="json") for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
        request_id=get_request_id(),
    )


@router.get(
    "/legal/amendment-reviews/{batch_id}",
    summary="Get one amendment review batch",
)
async def get_amendment_review(
    batch_id: UUID,
    config: BE2Config = Depends(get_config),
    repository: Any = Depends(get_amendment_review_repository),
    temporal_service: TemporalLawService = Depends(get_temporal_law_service),
    _: UserToken = Depends(require_roles(Role.ADMIN_PHAP_CHE)),
) -> dict[str, Any]:
    _require_amendment_review(config)
    batch = await _review_service(repository, temporal_service).get_review(str(batch_id))
    return success_response(data=batch.model_dump(mode="json"), request_id=get_request_id())


@router.patch(
    "/legal/amendment-reviews/{batch_id}/candidates/{candidate_id}",
    summary="Edit or decide one amendment candidate with revision guard",
)
async def update_amendment_candidate(
    batch_id: UUID,
    candidate_id: UUID,
    request: AmendmentCandidateUpdateRequest,
    config: BE2Config = Depends(get_config),
    repository: Any = Depends(get_amendment_review_repository),
    temporal_service: TemporalLawService = Depends(get_temporal_law_service),
    user: UserToken = Depends(require_roles(Role.ADMIN_PHAP_CHE)),
) -> dict[str, Any]:
    _require_amendment_review(config)
    mutable_fields = set(request.model_fields_set) - {"expected_revision"}
    if not mutable_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one candidate field must be supplied",
        )
    candidate = await _review_service(repository, temporal_service).update_candidate(
        batch_id=str(batch_id),
        candidate_id=str(candidate_id),
        expected_revision=request.expected_revision,
        actor_id=user.user_id,
        fields_set=mutable_fields,
        old_provision_id=request.old_provision_id,
        new_provision_id=request.new_provision_id,
        change_type=request.change_type,
        proposed_effective_from=request.proposed_effective_from,
        decision=request.decision,
        reviewer_note=request.reviewer_note,
    )
    return success_response(
        data=candidate.model_dump(mode="json"), request_id=get_request_id()
    )


@router.post(
    "/legal/amendment-reviews/{batch_id}/submit",
    summary="Submit a draft amendment batch for legal review",
)
async def submit_amendment_review(
    batch_id: UUID,
    request: AmendmentTransitionRequest,
    config: BE2Config = Depends(get_config),
    repository: Any = Depends(get_amendment_review_repository),
    temporal_service: TemporalLawService = Depends(get_temporal_law_service),
    user: UserToken = Depends(require_roles(Role.ADMIN_PHAP_CHE)),
) -> dict[str, Any]:
    _require_amendment_review(config)
    batch = await _review_service(repository, temporal_service).submit_review(
        batch_id=str(batch_id),
        expected_revision=request.expected_revision,
        actor_id=user.user_id,
    )
    return success_response(data=batch.model_dump(mode="json"), request_id=get_request_id())


@router.post(
    "/legal/amendment-reviews/{batch_id}/decision",
    summary="Approve or reject a submitted amendment review without graph commit",
)
async def decide_amendment_review(
    batch_id: UUID,
    request: AmendmentDecisionRequest,
    config: BE2Config = Depends(get_config),
    repository: Any = Depends(get_amendment_review_repository),
    temporal_service: TemporalLawService = Depends(get_temporal_law_service),
    user: UserToken = Depends(require_roles(Role.ADMIN_PHAP_CHE)),
) -> dict[str, Any]:
    _require_amendment_review(config)
    batch = await _review_service(repository, temporal_service).decide_review(
        batch_id=str(batch_id),
        expected_revision=request.expected_revision,
        actor_id=user.user_id,
        action=request.action,
        note=request.note,
    )
    return success_response(data=batch.model_dump(mode="json"), request_id=get_request_id())


@router.post(
    "/legal/amendment-reviews/{batch_id}/commit",
    summary="Commit an approved amendment atomically to the temporal legal graph",
)
async def commit_amendment_review(
    batch_id: UUID,
    request: AmendmentCommitRequest,
    config: BE2Config = Depends(get_config),
    review_repository: Any = Depends(get_amendment_review_repository),
    graph_repository: Any = Depends(get_amendment_commit_repository),
    temporal_service: TemporalLawService = Depends(get_temporal_law_service),
    user: UserToken = Depends(require_roles(Role.ADMIN_PHAP_CHE)),
) -> dict[str, Any]:
    _require_amendment_commit(config)
    report, batch, reconciled = await AmendmentCommitService(
        review_repository,
        temporal_service,
        graph_repository,
    ).commit_review(
        batch_id=str(batch_id),
        expected_revision=request.expected_revision,
        idempotency_key=request.idempotency_key,
        actor_id=user.user_id,
        amending_source_vb_id=request.amending_source_vb_id,
    )
    return success_response(
        data={
            "reconciled": reconciled,
            "report": report.model_dump(mode="json"),
            "batch": batch.model_dump(mode="json"),
        },
        request_id=get_request_id(),
    )
