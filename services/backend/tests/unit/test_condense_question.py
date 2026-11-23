"""Prior turns are passed into the agent prompt for reference resolution only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from backend.application.agents.research_agent.graph import GraphDeps, run_graph
from backend.application.agents.research_agent.prompts import (
    AnswerGenerationResult,
    build_agent_messages,
)
from backend.config import Settings
from backend.domain.answer import Answered, Citation, Question
from backend.domain.chunk import Chunk, ChunkId
from backend.domain.common import utc_now
from backend.domain.document import DocumentId
from backend.domain.engagement import EngagementId
from backend.domain.session import LlmUsage, SessionId, Turn, TurnId
from support.fakes import (
    FakeChatModel,
    FakeEmbedder,
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
    InMemoryEngagementRepository,
    InMemoryVectorIndex,
    agent_search_tool_turns,
)


def test_generation_messages_include_prior_answers_for_follow_ups() -> None:
    from backend.application.agents.research_agent.prompts import build_generation_messages

    prior = Turn(
        id=TurnId(uuid.uuid4()),
        session_id=SessionId(uuid.uuid4()),
        ordinal=0,
        question=Question(text="What is today's date?"),
        standalone_question="What is today's date?",
        answer=Answered(text="Today is Monday, 23 November 2026.", citations=()),
        created_at=utc_now(),
        usage=LlmUsage(),
    )
    messages = build_generation_messages(
        question="so what is it?",
        scored=(),
        auditor_role=None,
        topic=None,
        tool_facts=("current_time=2026-11-23T18:04:48+00:00\ntimezone=UTC\nweekday=Monday",),
        prior_turns=(prior,),
    )
    user = messages[1].content or ""
    assert "What is today's date?" in user
    assert "Today is Monday" in user
    assert "so what is it?" in user
    assert "current_time=" in user


def test_agent_messages_include_full_prior_history() -> None:
    prior = Turn(
        id=TurnId(uuid.uuid4()),
        session_id=SessionId(uuid.uuid4()),
        ordinal=0,
        question=Question(text="What is Contoso?"),
        standalone_question="What is Contoso supply agreement?",
        answer=Answered(
            text="A vendor [1]",
            citations=(
                Citation(
                    marker=1,
                    chunk_id=ChunkId(uuid.uuid4()),
                    document_id=DocumentId(uuid.uuid4()),
                    document_path="a.pdf",
                    snippet="Contoso",
                    score=0.9,
                ),
            ),
        ),
        created_at=utc_now(),
        usage=LlmUsage(),
    )
    messages = build_agent_messages(
        question="What are payment terms?",
        prior_turns=(prior,),
        auditor_role=None,
        topic=None,
        folder_scope=None,
    )
    user = messages[1].content or ""
    assert "What is Contoso supply agreement?" in user
    assert "A vendor [1]" in user
    assert "What are payment terms?" in user


async def test_follow_up_ask_still_retrieves_fresh_evidence() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    chunk = Chunk(
        id=ChunkId(uuid.uuid4()),
        document_id=DocumentId(uuid.uuid4()),
        document_version=1,
        ordinal=0,
        page=1,
        heading_path=(),
        text="Payment is due within thirty days.",
        token_count=6,
        created_at=datetime.now(UTC),
    )
    embedded = await embedder.embed((chunk.text,))
    await vector_index.upsert_chunks(
        engagement_id=engagement_id,
        document_id=chunk.document_id,
        document_path="contracts/a.pdf",
        document_version=1,
        chunks=(chunk,),
        embeddings=(embedded.vectors[0],),
        embedding_model=embedder.model_name,
    )
    chat = FakeChatModel(
        tool_turns=agent_search_tool_turns(),
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="Thirty days [1].",
            markers_used=(1,),
        ),
    )
    prior = Turn(
        id=TurnId(uuid.uuid4()),
        session_id=SessionId(uuid.uuid4()),
        ordinal=0,
        question=Question(text="earlier"),
        standalone_question="earlier standalone",
        answer=Answered(
            text="prior answer body must not be evidence",
            citations=(
                Citation(
                    marker=1,
                    chunk_id=ChunkId(uuid.uuid4()),
                    document_id=DocumentId(uuid.uuid4()),
                    document_path="other.pdf",
                    snippet="other",
                    score=0.5,
                ),
            ),
        ),
        created_at=utc_now(),
    )
    result = await run_graph(
        engagement_id=engagement_id,
        question=Question(text="payment terms?"),
        folder_scope=None,
        prior_turns=(prior,),
        deps=GraphDeps(
            chat=chat,
            embedder=embedder,
            vector_index=vector_index,
            engagements=InMemoryEngagementRepository(),
            documents=InMemoryDocumentRepository(),
            storage=InMemoryDocumentStorage(),
            settings=Settings(relevance_threshold=0.0),
        ),
    )
    assert result.answer.status == "answered"
    assert "prior answer body" not in result.answer.text
    first_user = chat.tool_turn_calls[0][0][1].content or ""
    assert "earlier standalone" in first_user
