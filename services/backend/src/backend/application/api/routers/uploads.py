"""Upload list and status routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query

from backend.application.api.contracts.v1.mapping import upload_to_response, upload_to_summary
from backend.application.api.contracts.v1.page import Page
from backend.application.api.contracts.v1.responses import UploadResponse, UploadSummaryResponse
from backend.application.api.dependencies import get_bound
from backend.application.get_upload import get_upload
from backend.application.list_uploads import list_uploads
from backend.bootstrap import SessionBound
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
    result = await list_uploads(
        bound.engagements,
        bound.uploads,
        engagement_id=engagement_id,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=tuple(upload_to_summary(item) for item in result.items),
        total=result.total,
        limit=limit,
        offset=offset,
    )


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
    result = await get_upload(
        bound.uploads,
        engagement_id=engagement_id,
        upload_id=UploadId(upload_id),
    )
    return upload_to_response(result.upload, list(result.items))
