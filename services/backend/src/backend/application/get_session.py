"""Load a session and its turns."""

from __future__ import annotations

from dataclasses import dataclass

from backend.application.ports import EngagementRepository, SessionRepository
from domain.engagement import EngagementId
from domain.errors import NotFoundError
from domain.session import Session, SessionId, Turn


@dataclass(frozen=True, slots=True)
class GetSessionResult:
    session: Session
    turns: tuple[Turn, ...]


async def get_session(
    engagements: EngagementRepository,
    sessions: SessionRepository,
    *,
    engagement_id: EngagementId,
    session_id: SessionId,
) -> GetSessionResult:
    engagement = await engagements.get(engagement_id)
    if engagement is None:
        raise NotFoundError(f"engagement not found: {engagement_id}")

    session = await sessions.get(engagement_id, session_id)
    if session is None:
        raise NotFoundError(f"session not found: {session_id}")

    turns = await sessions.list_turns(session_id)
    return GetSessionResult(session=session, turns=tuple(turns))