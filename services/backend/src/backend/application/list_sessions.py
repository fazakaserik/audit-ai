"""List chat sessions for an engagement."""

from __future__ import annotations

from dataclasses import dataclass

from backend.application.repositories.engagement import EngagementRepository
from backend.application.repositories.session import SessionRepository
from backend.domain.engagement import EngagementId
from backend.domain.errors import NotFoundError
from backend.domain.session import Session


@dataclass(frozen=True, slots=True)
class ListSessionsResult:
    items: tuple[Session, ...]
    total: int


async def list_sessions(
    engagements: EngagementRepository,
    sessions: SessionRepository,
    *,
    engagement_id: EngagementId,
    limit: int,
    offset: int,
) -> ListSessionsResult:
    engagement = await engagements.get(engagement_id)
    if engagement is None:
        raise NotFoundError(f"engagement not found: {engagement_id}")

    items, total = await sessions.list(engagement_id, limit=limit, offset=offset)
    return ListSessionsResult(items=tuple(items), total=total)
