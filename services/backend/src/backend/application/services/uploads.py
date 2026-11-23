"""Upload status application service."""

from __future__ import annotations

from backend.application.dto import Page, UploadDetail
from backend.application.repositories.engagement import EngagementRepository
from backend.application.repositories.upload import UploadRepository
from backend.domain.engagement import EngagementId
from backend.domain.errors import NotFoundError
from backend.domain.upload import Upload, UploadId


class UploadService:
    def __init__(
        self,
        engagements: EngagementRepository,
        uploads: UploadRepository,
    ) -> None:
        self._engagements = engagements
        self._uploads = uploads

    async def get_by_id(self, upload_id: UploadId) -> Upload | None:
        return await self._uploads.get_by_id(upload_id)

    async def mark_processing(self, upload_id: UploadId) -> None:
        await self._uploads.mark_processing(upload_id)

    async def refresh_status(self, upload_id: UploadId) -> Upload:
        return await self._uploads.refresh_status(upload_id)

    async def list_uploads(
        self,
        *,
        engagement_id: EngagementId,
        limit: int,
        offset: int,
    ) -> Page[Upload]:
        engagement = await self._engagements.get(engagement_id)
        if engagement is None:
            raise NotFoundError(f"engagement not found: {engagement_id}")

        items, total = await self._uploads.list(engagement_id, limit=limit, offset=offset)
        return Page(
            items=tuple(items),
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_upload(
        self,
        *,
        engagement_id: EngagementId,
        upload_id: UploadId,
    ) -> UploadDetail:
        loaded = await self._uploads.get(engagement_id, upload_id)
        if loaded is None:
            raise NotFoundError(f"upload not found: {upload_id}")
        upload, items = loaded
        return UploadDetail(upload=upload, items=tuple(items))
