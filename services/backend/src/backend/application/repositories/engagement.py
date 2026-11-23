"""Engagement repository protocol."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from backend.domain.engagement import Engagement, EngagementId


class EngagementRepository(Protocol):
    async def create(self, engagement: Engagement) -> Engagement: ...

    async def get(self, engagement_id: EngagementId) -> Engagement | None: ...

    async def update(self, engagement: Engagement) -> Engagement: ...

    async def delete(self, engagement_id: EngagementId) -> bool: ...

    async def list(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Engagement], int]: ...

    async def count_documents(self, engagement_id: EngagementId) -> int: ...

    async def count_documents_for_engagements(
        self,
        engagement_ids: Sequence[EngagementId],
    ) -> dict[EngagementId, int]: ...
