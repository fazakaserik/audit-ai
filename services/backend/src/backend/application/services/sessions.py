"""Session list and detail application service."""

from __future__ import annotations

from backend.application.dto import Page, SessionDetail
from backend.application.repositories.engagement import EngagementRepository
from backend.application.repositories.session import SessionRepository
from backend.domain.engagement import EngagementId
from backend.domain.errors import NotFoundError
from backend.domain.session import Session, SessionId


class SessionService:
    def __init__(
        self,
        engagements: EngagementRepository,
        sessions: SessionRepository,
    ) -> None:
        self._engagements = engagements
        self._sessions = sessions

    async def list_sessions(
        self,
        *,
        engagement_id: EngagementId,
        limit: int,
        offset: int,
    ) -> Page[Session]:
        limit = min(max(limit, 1), 200)
        offset = max(offset, 0)
        engagement = await self._engagements.get(engagement_id)
        if engagement is None:
            raise NotFoundError(f"engagement not found: {engagement_id}")

        items, total = await self._sessions.list(engagement_id, limit=limit, offset=offset)
        return Page(
            items=tuple(items),
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_session(
        self,
        *,
        engagement_id: EngagementId,
        session_id: SessionId,
    ) -> SessionDetail:
        engagement = await self._engagements.get(engagement_id)
        if engagement is None:
            raise NotFoundError(f"engagement not found: {engagement_id}")

        session = await self._sessions.get(engagement_id, session_id)
        if session is None:
            raise NotFoundError(f"session not found: {session_id}")

        turns = await self._sessions.list_turns(session_id)
        return SessionDetail(session=session, turns=tuple(turns))
