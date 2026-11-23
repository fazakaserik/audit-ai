"""Engagement application service."""

from __future__ import annotations

from backend.application.api.contracts.v1.mapping import engagement_to_response
from backend.application.api.contracts.v1.page import Page
from backend.application.api.contracts.v1.responses import EngagementResponse
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
    ) -> EngagementResponse:
        now = utc_now()
        engagement = Engagement(
            id=engagement_id,
            name=name,
            created_at=now,
            updated_at=now,
        )
        created = await self._engagements.create(engagement)
        return engagement_to_response(created, document_count=0)

    async def list(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Page[EngagementResponse]:
        limit = min(max(limit, 1), 200)
        offset = max(offset, 0)
        items, total = await self._engagements.list(limit=limit, offset=offset)
        responses: list[EngagementResponse] = []
        for eng in items:
            count = await self._engagements.count_documents(eng.id)
            responses.append(engagement_to_response(eng, document_count=count))
        return Page(items=tuple(responses), total=total, limit=limit, offset=offset)

    async def get(self, *, engagement_id: EngagementId) -> EngagementResponse:
        eng = await self._engagements.get(engagement_id)
        if eng is None:
            raise NotFoundError(f"engagement not found: {engagement_id}")
        count = await self._engagements.count_documents(eng.id)
        return engagement_to_response(eng, document_count=count)
