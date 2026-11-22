"""Ask a grounded question and persist the session turn."""

from __future__ import annotations

from backend.application.ports import (
    AskResult,
    AskSessionBound,
    ChatModel,
    Embedder,
    SessionRepository,
)
from backend.config import Settings
from backend.rag.graph import run_ask_graph
from backend.rag.nodes import AskGraphDeps
from domain.answer import Question
from domain.common import new_uuid, utc_now
from domain.engagement import EngagementId
from domain.errors import NotFoundError
from domain.session import Session, SessionId, Turn, TurnId


def _title_from_question(text: str) -> str:
    stripped = text.strip()
    if len(stripped) <= 200:
        return stripped
    return stripped[:199].rstrip() + "…"


async def ask_question(
    bound: AskSessionBound,
    *,
    chat: ChatModel,
    embedder: Embedder,
    settings: Settings,
    engagement_id: EngagementId,
    question: Question,
    session_id: SessionId | None,
) -> AskResult:
    engagement = await bound.engagements.get(engagement_id)
    if engagement is None:
        raise NotFoundError(f"engagement not found: {engagement_id}")

    sessions: SessionRepository = bound.sessions
    now = utc_now()

    if session_id is None:
        session = Session(
            id=SessionId(new_uuid()),
            engagement_id=engagement_id,
            title=_title_from_question(question.text),
            turn_count=0,
            created_at=now,
            updated_at=now,
        )
        session = await sessions.create(session)
    else:
        session = await sessions.get(engagement_id, session_id)
        if session is None:
            raise NotFoundError(f"session not found: {session_id}")

    prior_turns = await sessions.list_turns(session.id)

    deps = AskGraphDeps(
        chat=chat,
        embedder=embedder,
        vector_index=bound.vector_index,
        settings=settings,
    )
    graph_result = await run_ask_graph(
        engagement_id=engagement_id,
        question=question,
        folder_scope=question.folder_scope,
        prior_turns=prior_turns,
        deps=deps,
    )

    turn = Turn(
        id=TurnId(new_uuid()),
        session_id=session.id,
        ordinal=session.turn_count,
        question=question,
        standalone_question=graph_result.standalone_question,
        answer=graph_result.answer,
        created_at=now,
    )
    await sessions.add_turn(turn)

    title_update = _title_from_question(question.text) if session.turn_count == 0 else None
    await sessions.bump_turn_count(session.id, title=title_update)

    return AskResult(
        answer=graph_result.answer,
        session_id=session.id,
        turn_id=turn.id,
        standalone_question=graph_result.standalone_question,
    )