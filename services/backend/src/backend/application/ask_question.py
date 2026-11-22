"""Ask a grounded question and persist the session turn."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

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
from backend.rag.progress import CollectingAskProgress
from domain.answer import Answer, Question
from domain.common import new_uuid, utc_now
from domain.engagement import EngagementId
from domain.errors import NotFoundError
from domain.session import LlmUsage, Session, SessionId, Turn, TurnId


def _session_total_tokens(prior_turns: Sequence[Turn], usage: LlmUsage) -> int:
    prior = sum(turn.usage.total_tokens for turn in prior_turns if turn.usage is not None)
    return prior + usage.total_tokens


def _title_from_question(text: str) -> str:
    stripped = text.strip()
    if len(stripped) <= 200:
        return stripped
    return stripped[:199].rstrip() + "…"


async def _prepare_session(
    bound: AskSessionBound,
    *,
    engagement_id: EngagementId,
    question: Question,
    session_id: SessionId | None,
) -> tuple[Session, Sequence[Turn]]:
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
    return session, prior_turns


def _thinking_from_progress(
    progress: CollectingAskProgress | None,
) -> tuple[str | None, float | None]:
    if progress is None:
        return None, None
    text = "".join(progress.thinking_chunks).strip() or None
    seconds = round(progress.thinking_seconds, 1) if progress.thinking_seconds > 0 else None
    return text, seconds


async def _persist_turn(
    bound: AskSessionBound,
    *,
    session: Session,
    question: Question,
    answer: Answer,
    standalone_question: str,
    usage: LlmUsage,
    prior_turns: Sequence[Turn],
    progress: CollectingAskProgress | None = None,
) -> AskResult:
    sessions: SessionRepository = bound.sessions
    now = utc_now()
    thinking_text, thinking_seconds = _thinking_from_progress(progress)
    turn = Turn(
        id=TurnId(new_uuid()),
        session_id=session.id,
        ordinal=session.turn_count,
        question=question,
        standalone_question=standalone_question,
        answer=answer,
        created_at=now,
        thinking_text=thinking_text,
        thinking_seconds=thinking_seconds,
        usage=usage,
    )
    await sessions.add_turn(turn)
    title_update = _title_from_question(question.text) if session.turn_count == 0 else None
    await sessions.bump_turn_count(session.id, title=title_update)
    return AskResult(
        answer=answer,
        session_id=session.id,
        turn_id=turn.id,
        standalone_question=standalone_question,
        usage=usage,
        session_total_tokens=_session_total_tokens(prior_turns, usage),
    )


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
    session, prior_turns = await _prepare_session(
        bound,
        engagement_id=engagement_id,
        question=question,
        session_id=session_id,
    )
    progress = CollectingAskProgress()
    deps = AskGraphDeps(
        chat=chat,
        embedder=embedder,
        vector_index=bound.vector_index,
        settings=settings,
        progress=progress,
    )
    graph_result = await run_ask_graph(
        engagement_id=engagement_id,
        question=question,
        folder_scope=question.folder_scope,
        prior_turns=prior_turns,
        deps=deps,
    )
    return await _persist_turn(
        bound,
        session=session,
        question=question,
        answer=graph_result.answer,
        standalone_question=graph_result.standalone_question,
        usage=graph_result.usage,
        prior_turns=prior_turns,
        progress=progress,
    )


async def ask_question_stream(
    bound: AskSessionBound,
    *,
    chat: ChatModel,
    embedder: Embedder,
    settings: Settings,
    engagement_id: EngagementId,
    question: Question,
    session_id: SessionId | None,
) -> AsyncIterator[dict[str, object]]:
    """Yield progress event dicts, then a final result dict (or error)."""
    queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()

    async def emit(event: dict[str, object]) -> None:
        await queue.put(event)

    progress = CollectingAskProgress()
    progress.bind_emitter(emit)

    async def run() -> None:
        try:
            session, prior_turns = await _prepare_session(
                bound,
                engagement_id=engagement_id,
                question=question,
                session_id=session_id,
            )
            deps = AskGraphDeps(
                chat=chat,
                embedder=embedder,
                vector_index=bound.vector_index,
                settings=settings,
                progress=progress,
            )
            graph_result = await run_ask_graph(
                engagement_id=engagement_id,
                question=question,
                folder_scope=question.folder_scope,
                prior_turns=prior_turns,
                deps=deps,
            )
            if progress.thinking_seconds > 0 or progress.thinking_chunks:
                await emit(
                    {
                        "type": "thinking_done",
                        "duration_seconds": round(progress.thinking_seconds, 1),
                    }
                )
            result = await _persist_turn(
                bound,
                session=session,
                question=question,
                answer=graph_result.answer,
                standalone_question=graph_result.standalone_question,
                usage=graph_result.usage,
                prior_turns=prior_turns,
                progress=progress,
            )
            await emit({"type": "final", "result": result})
        except Exception as exc:
            await emit({"type": "error", "error": exc})
        finally:
            await queue.put(None)

    task = asyncio.create_task(run())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        await task
