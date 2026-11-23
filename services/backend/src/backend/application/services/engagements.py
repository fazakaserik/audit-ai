"""Engagement application service."""

from __future__ import annotations

from backend.application.dto import EngagementWithDocumentCount, Page
from backend.application.repositories.engagement import EngagementRepository
from backend.domain.common import utc_now
from backend.domain.engagement import Engagement, EngagementId
from backend.domain.errors import NotFoundError


class EngagementService:
    def __init__(self, engagements: EngagementRepository) -> None:
        self._engagements = engagements

    async def create(
        self,
        *,
        engagement_id: EngagementId,
        name: str,
    ) -> EngagementWithDocumentCount:
        now = utc_now()
        engagement = Engagement(
            id=engagement_id,
            name=name,
            created_at=now,
            updated_at=now,
        )
        created = await self._engagements.create(engagement)
        return EngagementWithDocumentCount(engagement=created, document_count=0)

    async def list(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Page[EngagementWithDocumentCount]:
        limit = min(max(limit, 1), 200)
        offset = max(offset, 0)
        items, total = await self._engagements.list(limit=limit, offset=offset)
        counts = await self._engagements.count_documents_for_engagements([e.id for e in items])
        views = tuple(
            EngagementWithDocumentCount(engagement=eng, document_count=counts.get(eng.id, 0))
            for eng in items
        )
        return Page(items=views, total=total, limit=limit, offset=offset)

    async def get(self, *, engagement_id: EngagementId) -> EngagementWithDocumentCount:
        eng = await self._engagements.get(engagement_id)
        if eng is None:
            raise NotFoundError(f"engagement not found: {engagement_id}")
        count = await self._engagements.count_documents(eng.id)
        return EngagementWithDocumentCount(engagement=eng, document_count=count)
