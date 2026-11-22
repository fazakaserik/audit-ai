"""Load upload status and per-file outcomes."""

from __future__ import annotations

from dataclasses import dataclass

from backend.application.ports import UploadRepository
from domain.engagement import EngagementId
from domain.errors import NotFoundError
from domain.upload import Upload, UploadId, UploadItem


@dataclass(frozen=True, slots=True)
class GetUploadResult:
    upload: Upload
    items: tuple[UploadItem, ...]


async def get_upload(
    uploads: UploadRepository,
    *,
    engagement_id: EngagementId,
    upload_id: UploadId,
) -> GetUploadResult:
    loaded = await uploads.get(engagement_id, upload_id)
    if loaded is None:
        raise NotFoundError(f"upload not found: {upload_id}")
    upload, items = loaded
    return GetUploadResult(upload=upload, items=tuple(items))