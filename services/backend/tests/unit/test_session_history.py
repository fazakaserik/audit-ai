"""Session history window, summary fallback, and evidence budget."""

from __future__ import annotations

import uuid

from backend.application.agents.research_agent.history import (
    HistorySummaryResult,
    prepare_session_context,
)
from backend.application.agents.research_agent.prompts import (
    build_agent_messages,
    build_generation_messages,
)
from backend.application.dto import ScoredChunk
from backend.domain.answer import Answered, Question
from backend.domain.chunk import Chunk, ChunkId
from backend.domain.common import utc_now
from backend.domain.document import DocumentId
from backend.domain.errors import ModelUnavailableError
from backend.domain.session import LlmUsage, SessionId, Turn, TurnId
from support.fakes import FakeChatModel


def _turn(ordinal: int, *, question: str, answer: str) -> Turn:
    return Turn(
        id=TurnId(uuid.uuid4()),
        session_id=SessionId(uuid.uuid4()),
        ordinal=ordinal,
        question=Question(text=question),
        standalone_question=question,
        answer=Answered(text=answer, citations=()),
        created_at=utc_now(),
        usage=LlmUsage(),
    )


async def test_prepare_session_context_keeps_recent_and_summarizes_older() -> None:
    turns = tuple(_turn(i, question=f"Q{i}", answer=f"A{i} " + ("x" * 80)) for i in range(7))
    chat = FakeChatModel(response=HistorySummaryResult(summary="Earlier covered Q0-Q1."))
    context, usage = await prepare_session_context(turns, max_recent=5, chat=chat)
    assert len(context.recent_turns) == 5
    assert context.recent_turns[0].standalone_question == "Q2"
    assert context.older_summary == "Earlier covered Q0-Q1."
    assert usage.total_tokens > 0


async def test_prepare_session_context_falls_back_when_summary_model_fails() -> None:
    turns = tuple(_turn(i, question=f"Q{i}", answer=f"A{i}") for i in range(6))
    chat = FakeChatModel(error=ModelUnavailableError("summary unavailable"))
    context, usage = await prepare_session_context(turns, max_recent=5, chat=chat)
    assert len(context.recent_turns) == 5
    assert context.older_summary is not None
    assert "Q0" in context.older_summary
    assert usage.total_tokens == 0


def test_agent_messages_include_older_summary() -> None:
    recent = (_turn(5, question="latest?", answer="yes"),)
    messages = build_agent_messages(
        question="follow up?",
        prior_turns=recent,
        auditor_role=None,
        topic=None,
        folder_scope=None,
        older_summary="Discussed Contoso payment terms earlier.",
    )
    user = messages[1].content or ""
    assert "Earlier session summary: Discussed Contoso payment terms earlier." in user
    assert "latest?" in user
    assert "full session" not in user


def test_generation_messages_respect_evidence_char_budget() -> None:
    doc_id = DocumentId(uuid.uuid4())
    chunk = Chunk(
        id=ChunkId(uuid.uuid4()),
        document_id=doc_id,
        document_version=1,
        ordinal=0,
        page=1,
        heading_path=(),
        text="A" * 5_000,
        token_count=100,
        created_at=utc_now(),
    )
    scored = (
        ScoredChunk(chunk=chunk, score=0.9, document_path="big.md"),
        ScoredChunk(
            chunk=Chunk(
                id=ChunkId(uuid.uuid4()),
                document_id=doc_id,
                document_version=1,
                ordinal=1,
                page=2,
                heading_path=(),
                text="B" * 5_000,
                token_count=100,
                created_at=utc_now(),
            ),
            score=0.8,
            document_path="big.md",
        ),
    )
    messages = build_generation_messages(
        question="what?",
        scored=scored,
        auditor_role=None,
        topic=None,
        evidence_max_chars=1_500,
    )
    user = messages[1].content or ""
    assert "Source chunks:" in user
    assert len(user) < 3_000
    assert "A" in user
