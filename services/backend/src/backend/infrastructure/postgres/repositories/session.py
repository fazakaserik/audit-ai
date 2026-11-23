"""Postgres session repository adapter."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.domain.engagement import EngagementId
from backend.domain.errors import NotFoundError
from backend.domain.session import Session, SessionId, Turn
from backend.infrastructure.postgres.models import SessionRow, SessionTurnRow
from backend.infrastructure.postgres.repositories._mappers import (
    populate_answer_rows,
    session_from_row,
    turn_from_row,
)


class PostgresSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, session: Session) -> Session:
        row = SessionRow(
            id=session.id,
            engagement_id=session.engagement_id,
            title=session.title,
            turn_count=session.turn_count,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return session_from_row(row)

    async def get(
        self,
        engagement_id: EngagementId,
        session_id: SessionId,
    ) -> Session | None:
        stmt = select(SessionRow).where(
            SessionRow.id == session_id,
            SessionRow.engagement_id == engagement_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return session_from_row(row)

    async def list(
        self,
        engagement_id: EngagementId,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Session], int]:
        filters = [SessionRow.engagement_id == engagement_id]
        total_stmt = select(func.count()).select_from(SessionRow).where(*filters)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(SessionRow)
            .where(*filters)
            .order_by(SessionRow.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [session_from_row(row) for row in rows], total

    async def add_turn(self, turn: Turn) -> Turn:
        usage = turn.usage
        row = SessionTurnRow(
            id=turn.id,
            session_id=turn.session_id,
            ordinal=turn.ordinal,
            question_text=turn.question.text,
            question_folder_scope=turn.question.folder_scope,
            question_auditor_role=turn.question.auditor_role,
            question_topic=turn.question.topic,
            standalone_question=turn.standalone_question,
            answer_status=turn.answer.status.value,
            answer_text=None,
            insufficient_reason=None,
            thinking_text=turn.thinking_text,
            thinking_seconds=turn.thinking_seconds,
            usage_prompt_tokens=usage.prompt_tokens if usage is not None else None,
            usage_completion_tokens=usage.completion_tokens if usage is not None else None,
            usage_total_tokens=usage.total_tokens if usage is not None else None,
            created_at=turn.created_at,
            citations=[],
            suggested_questions=[],
        )
        populate_answer_rows(row, turn.answer)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(
            row,
            attribute_names=["citations", "suggested_questions"],
        )
        return turn_from_row(row)

    async def list_turns(self, session_id: SessionId) -> list[Turn]:
        stmt = (
            select(SessionTurnRow)
            .where(SessionTurnRow.session_id == session_id)
            .options(
                selectinload(SessionTurnRow.citations),
                selectinload(SessionTurnRow.suggested_questions),
            )
            .order_by(SessionTurnRow.ordinal.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [turn_from_row(row) for row in rows]

    async def bump_turn_count(
        self,
        session_id: SessionId,
        *,
        title: str | None = None,
    ) -> Session:
        row = await self._session.get(SessionRow, session_id)
        if row is None:
            raise NotFoundError(f"session not found: {session_id}")
        row.turn_count += 1
        row.updated_at = datetime.now(UTC)
        if title is not None:
            row.title = title
        await self._session.flush()
        return session_from_row(row)
