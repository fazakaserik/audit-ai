"""Upload repository protocol."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from backend.domain.engagement import EngagementId
from backend.domain.upload import Upload, UploadId, UploadItem


class UploadRepository(Protocol):
    async def create(self, upload: Upload, items: Sequence[UploadItem]) -> Upload: ...

    async def get(
        self,
        engagement_id: EngagementId,
        upload_id: UploadId,
    ) -> tuple[Upload, list[UploadItem]] | None: ...

    async def get_by_id(self, upload_id: UploadId) -> Upload | None: ...

    async def list(
        self,
        engagement_id: EngagementId,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Upload], int]: ...

    async def mark_processing(self, upload_id: UploadId) -> None: ...

    async def refresh_status(self, upload_id: UploadId) -> Upload: ...
