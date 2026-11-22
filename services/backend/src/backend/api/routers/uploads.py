"""Upload status routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from backend.api.contracts.v1.mapping import upload_to_response
from backend.api.contracts.v1.responses import UploadResponse
from backend.api.dependencies import get_bound
from backend.application.get_upload import get_upload
from backend.bootstrap import SessionBound
from domain.engagement import EngagementId
from domain.upload import UploadId

router = APIRouter(prefix="/api/v1/engagements", tags=["uploads"])


@router.get("/{engagement_id}/uploads/{upload_id}", response_model=UploadResponse)
async def get_upload_status(
    engagement_id: EngagementId,
    upload_id: UUID,
    bound: Annotated[SessionBound, Depends(get_bound)],
) -> UploadResponse:
    result = await get_upload(
        bound.uploads,
        engagement_id=engagement_id,
        upload_id=UploadId(upload_id),
    )
    return upload_to_response(result.upload, list(result.items))