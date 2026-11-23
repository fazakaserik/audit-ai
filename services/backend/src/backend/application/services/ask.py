"""Ask-question application service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

from backend.application.agents.progress import CollectingAskProgress
from backend.application.dto import (
    AskResult,
    AskStreamError,
    AskStreamEvent,
    AskStreamFinal,
    AskStreamThinkingDone,
)
from backend.application.llm.chat_model import ChatModel
from backend.application.llm.embedder import Embedder
from backend.application.repositories.document import DocumentRepository
from backend.application.repositories.engagement import EngagementRepository
from backend.application.repositories.session import SessionRepository
from backend.application.storage.document_storage import DocumentStorage
from backend.application.storage.vector_index import VectorIndex
from backend.config import Settings
from backend.domain.answer import Answer, Question
from backend.domain.common import new_uuid, utc_now
from backend.domain.engagement import EngagementId
from backend.domain.errors import NotFoundError
from backend.domain.session import LlmUsage, Session, SessionId, Turn, TurnId


def _session_total_tokens(prior_turns: Sequence[Turn], usage: LlmUsage) -> int:
    prior = sum(turn.usage.total_tokens for turn in prior_turns if turn.usage is not None)
    return prior + usage.total_tokens


def _title_from_question(text: str) -> str:
    stripped = text.strip()
    if len(stripped) <= 200:
        return stripped
    return stripped[:199].rstrip() + "…"


def _thinking_from_progress(
    progress: CollectingAskProgress | None,
) -> tuple[str | None, float | None]:
    if progress is None:
        return None, None
    text = "".join(progress.thinking_chunks).strip() or None
    seconds = round(progress.thinking_seconds, 1) if progress.thinking_seconds > 0 else None
    return text, seconds


class AskService:
    def __init__(
        self,
        engagements: EngagementRepository,
        documents: DocumentRepository,
        sessions: SessionRepository,
        vector_index: VectorIndex,
        chat: ChatModel,
        embedder: Embedder,
        storage: DocumentStorage,
        settings: Settings,
    ) -> None:
        self._engagements = engagements
        self._documents = documents
        self._sessions = sessions
        self._vector_index = vector_index
        self._chat = chat
        self._embedder = embedder
        self._storage = storage
        self._settings = settings

    async def _prepare_session(
        self,
        *,
        engagement_id: EngagementId,
        question: Question,
        session_id: SessionId | None,
    ) -> tuple[Session, Sequence[Turn]]:
        engagement = await self._engagements.get(engagement_id)
        if engagement is None:
            raise NotFoundError(f"engagement not found: {engagement_id}")

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
            session = await self._sessions.create(session)
        else:
            session = await self._sessions.get(engagement_id, session_id)
            if session is None:
                raise NotFoundError(f"session not found: {session_id}")

        prior_turns = await self._sessions.list_turns(session.id)
        return session, prior_turns

    async def _persist_turn(
        self,
        *,
        session: Session,
        question: Question,
        answer: Answer,
        standalone_question: str,
        usage: LlmUsage,
        prior_turns: Sequence[Turn],
        progress: CollectingAskProgress | None = None,
    ) -> AskResult:
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
        await self._sessions.add_turn(turn)
        title_update = _title_from_question(question.text) if session.turn_count == 0 else None
        await self._sessions.bump_turn_count(session.id, title=title_update)
        return AskResult(
            answer=answer,
            session_id=session.id,
            turn_id=turn.id,
            standalone_question=standalone_question,
            usage=usage,
            session_total_tokens=_session_total_tokens(prior_turns, usage),
        )

    def _graph_deps(self, progress: CollectingAskProgress):
        from backend.application.agents.research_agent.graph import GraphDeps

        return GraphDeps(
            chat=self._chat,
            embedder=self._embedder,
            vector_index=self._vector_index,
            engagements=self._engagements,
            documents=self._documents,
            storage=self._storage,
            settings=self._settings,
            progress=progress,
        )

    async def _run_ask(
        self,
        *,
        engagement_id: EngagementId,
        question: Question,
        session_id: SessionId | None,
        progress: CollectingAskProgress,
    ) -> AskResult:
        from backend.application.agents.research_agent.graph import run_graph

        session, prior_turns = await self._prepare_session(
            engagement_id=engagement_id,
            question=question,
            session_id=session_id,
        )
        graph_result = await run_graph(
            engagement_id=engagement_id,
            question=question,
            folder_scope=question.folder_scope,
            prior_turns=prior_turns,
            deps=self._graph_deps(progress),
        )
        return await self._persist_turn(
            session=session,
            question=question,
            answer=graph_result.answer,
            standalone_question=graph_result.standalone_question,
            usage=graph_result.usage,
            prior_turns=prior_turns,
            progress=progress,
        )

    async def ask_question(
        self,
        *,
        engagement_id: EngagementId,
        question: Question,
        session_id: SessionId | None,
    ) -> AskResult:
        progress = CollectingAskProgress()
        return await self._run_ask(
            engagement_id=engagement_id,
            question=question,
            session_id=session_id,
            progress=progress,
        )

    async def ask_question_stream(
        self,
        *,
        engagement_id: EngagementId,
        question: Question,
        session_id: SessionId | None,
    ) -> AsyncIterator[AskStreamEvent]:
        """Yield progress events, then AskStreamFinal or AskStreamError."""
        queue: asyncio.Queue[AskStreamEvent | None] = asyncio.Queue()

        async def emit(event: dict[str, object]) -> None:
            await queue.put(event)

        progress = CollectingAskProgress()
        progress.bind_emitter(emit)

        async def run() -> None:
            try:
                result = await self._run_ask(
                    engagement_id=engagement_id,
                    question=question,
                    session_id=session_id,
                    progress=progress,
                )
                if progress.thinking_seconds > 0 or progress.thinking_chunks:
                    await queue.put(
                        AskStreamThinkingDone(
                            duration_seconds=round(progress.thinking_seconds, 1),
                        )
                    )
                await queue.put(AskStreamFinal(result=result))
            except Exception as exc:
                await queue.put(AskStreamError(error=exc))
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
