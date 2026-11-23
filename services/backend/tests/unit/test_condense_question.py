"""Prior turns are passed into the agent prompt for reference resolution only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from backend.config import Settings
from backend.rag.agent import AskAgentDeps, run_ask_agent
from backend.rag.prompts import AnswerGenerationResult, build_agent_messages
from domain.answer import Answered, Citation, Question
from domain.common import utc_now
from domain.document import DocumentId
from domain.engagement import EngagementId
from domain.chunk import Chunk, ChunkId
from domain.session import LlmUsage, SessionId, Turn, TurnId
from support.fakes import (
    FakeChatModel,
    FakeEmbedder,
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
    InMemoryEngagementRepository,
    InMemoryVectorIndex,
)


def test_agent_messages_include_prior_questions_not_answers() -> None:
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
    assert "A vendor" not in user
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
    result = await run_ask_agent(
        engagement_id=engagement_id,
        question=Question(text="payment terms?"),
        folder_scope=None,
        prior_turns=(prior,),
        deps=AskAgentDeps(
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
