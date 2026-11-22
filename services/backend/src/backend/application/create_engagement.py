"""Create engagement use case."""

from __future__ import annotations

from backend.application.ports import EngagementRepository
from domain.common import utc_now
from domain.engagement import Engagement, EngagementId


async def create_engagement(
    repo: EngagementRepository,
    *,
    engagement_id: EngagementId,
    name: str,
) -> Engagement:
    now = utc_now()
    engagement = Engagement(
        id=engagement_id,
        name=name,
        created_at=now,
        updated_at=now,
    )
    return await repo.create(engagement)
