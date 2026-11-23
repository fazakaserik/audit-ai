"""Upload list and status controllers."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query

from backend.application.api.contracts.v1.mapping import (
    to_contract_page,
    upload_detail_to_response,
    upload_to_summary,
)
from backend.application.api.contracts.v1.page import Page
from backend.application.api.contracts.v1.responses import UploadResponse, UploadSummaryResponse
from backend.application.api.dependencies import get_bound
from backend.application.wiring import SessionBound
from backend.domain.engagement import EngagementId
from backend.domain.upload import UploadId

router = APIRouter(prefix="/api/v1/engagements", tags=["uploads"])


@router.get(
    "/{engagement_id}/uploads",
    response_model=Page[UploadSummaryResponse],
    summary="List uploads",
)
async def get_uploads_list(
    engagement_id: Annotated[
        EngagementId,
        Path(description="Engagement whose upload jobs to list"),
    ],
    bound: Annotated[SessionBound, Depends(get_bound)],
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Max uploads to return"),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0, description="Number of uploads to skip"),
    ] = 0,
) -> Page[UploadSummaryResponse]:
    """List upload jobs for an engagement, newest first."""
    page = await bound.uploads.list_uploads(
        engagement_id=engagement_id,
        limit=limit,
        offset=offset,
    )
    return to_contract_page(page, upload_to_summary)


@router.get(
    "/{engagement_id}/uploads/{upload_id}",
    response_model=UploadResponse,
    summary="Get upload details",
)
async def get_upload_status(
    engagement_id: Annotated[
        EngagementId,
        Path(description="Engagement that owns the upload"),
    ],
    upload_id: Annotated[
        UUID,
        Path(description="Upload job to inspect"),
    ],
    bound: Annotated[SessionBound, Depends(get_bound)],
) -> UploadResponse:
    """Return upload status and per-file outcomes."""
    detail = await bound.uploads.get_upload(
        engagement_id=engagement_id,
        upload_id=UploadId(upload_id),
    )
    return upload_detail_to_response(detail)
