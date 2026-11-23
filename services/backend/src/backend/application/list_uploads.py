"""List upload jobs for an engagement."""

from __future__ import annotations

from dataclasses import dataclass

from backend.application.repositories.engagement import EngagementRepository
from backend.application.repositories.upload import UploadRepository
from backend.domain.engagement import EngagementId
from backend.domain.errors import NotFoundError
from backend.domain.upload import Upload


@dataclass(frozen=True, slots=True)
class ListUploadsResult:
    items: tuple[Upload, ...]
    total: int


async def list_uploads(
    engagements: EngagementRepository,
    uploads: UploadRepository,
    *,
    engagement_id: EngagementId,
    limit: int,
    offset: int,
) -> ListUploadsResult:
    engagement = await engagements.get(engagement_id)
    if engagement is None:
        raise NotFoundError(f"engagement not found: {engagement_id}")

    items, total = await uploads.list(engagement_id, limit=limit, offset=offset)
    return ListUploadsResult(items=tuple(items), total=total)
