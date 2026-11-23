"""Engagement repository protocol."""

from __future__ import annotations

from typing import Protocol

from backend.domain.engagement import Engagement, EngagementId


class EngagementRepository(Protocol):
    async def create(self, engagement: Engagement) -> Engagement: ...

    async def get(self, engagement_id: EngagementId) -> Engagement | None: ...

    async def list(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Engagement], int]: ...

    async def count_documents(self, engagement_id: EngagementId) -> int: ...
