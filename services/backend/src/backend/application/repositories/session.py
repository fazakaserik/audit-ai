"""Session repository protocol."""

from __future__ import annotations

from typing import Protocol

from backend.domain.engagement import EngagementId
from backend.domain.session import Session, SessionId, Turn


class SessionRepository(Protocol):
    async def create(self, session: Session) -> Session: ...

    async def get(
        self,
        engagement_id: EngagementId,
        session_id: SessionId,
    ) -> Session | None: ...

    async def list(
        self,
        engagement_id: EngagementId,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Session], int]: ...

    async def add_turn(self, turn: Turn) -> Turn: ...

    async def list_turns(self, session_id: SessionId) -> list[Turn]: ...

    async def bump_turn_count(
        self, session_id: SessionId, *, title: str | None = None
    ) -> Session: ...
