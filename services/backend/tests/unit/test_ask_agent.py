"""Unit tests for the tool-calling ask agent."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from backend.application.ports import ToolCall, ToolTurnResult
from backend.application.rag.agent import AskAgentDeps, run_ask_agent
from backend.application.rag.prompts import AnswerGenerationResult
from backend.config import Settings
from backend.domain.answer import AnswerStatus, InsufficientReason, Question
from backend.domain.chunk import Chunk, ChunkId
from backend.domain.document import ContentType, Document, DocumentId, DocumentPath
from backend.domain.engagement import EngagementId
from backend.domain.session import LlmUsage
from support.fakes import (
    FakeChatModel,
    FakeEmbedder,
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
    InMemoryEngagementRepository,
    InMemoryVectorIndex,
)


def _settings(*, agent_max_tool_rounds: int = 6) -> Settings:
    return Settings(
        relevance_threshold=0.0,
        retrieval_top_k=8,
        agent_max_tool_rounds=agent_max_tool_rounds,
    )


async def _index(
    vector_index: InMemoryVectorIndex,
    embedder: FakeEmbedder,
    *,
    engagement_id: EngagementId,
    path: str,
    text: str,
) -> Chunk:
    doc_id = DocumentId(uuid.uuid4())
    chunk = Chunk(
        id=ChunkId(uuid.uuid4()),
        document_id=doc_id,
        document_version=1,
        ordinal=0,
        page=1,
        heading_path=(),
        text=text,
        token_count=max(1, len(text.split())),
        created_at=datetime.now(UTC),
    )
    embedded = await embedder.embed((text,))
    await vector_index.upsert_chunks(
        engagement_id=engagement_id,
        document_id=doc_id,
        document_path=path,
        document_version=1,
        chunks=(chunk,),
        embeddings=(embedded.vectors[0],),
        embedding_model=embedder.model_name,
    )
    return chunk


def _deps(
    *,
    chat: FakeChatModel,
    embedder: FakeEmbedder | None = None,
    vector_index: InMemoryVectorIndex | None = None,
    engagements: InMemoryEngagementRepository | None = None,
    documents: InMemoryDocumentRepository | None = None,
    storage: InMemoryDocumentStorage | None = None,
    settings: Settings | None = None,
) -> AskAgentDeps:
    return AskAgentDeps(
        chat=chat,
        embedder=embedder or FakeEmbedder(),
        vector_index=vector_index or InMemoryVectorIndex(),
        engagements=engagements or InMemoryEngagementRepository(),
        documents=documents or InMemoryDocumentRepository(),
        storage=storage or InMemoryDocumentStorage(),
        settings=settings or _settings(),
    )


async def test_agent_search_then_answer_with_citations() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await _index(
        vector_index,
        embedder,
        engagement_id=engagement_id,
        path="contracts/a.pdf",
        text="Payment is due within thirty days.",
    )
    chat = FakeChatModel(
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="Thirty days [1].",
            markers_used=(1,),
        ),
        usage=LlmUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )
    result = await run_ask_agent(
        engagement_id=engagement_id,
        question=Question(text="What are the payment terms?"),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(chat=chat, embedder=embedder, vector_index=vector_index),
    )
    assert result.answer.status == AnswerStatus.ANSWERED
    assert result.answer.citations[0].snippet.startswith("Payment is due")
    assert chat.tool_turn_calls
    first_tools = chat.tool_turn_calls[0][1]
    assert any(spec.name == "search_relevant_chunks" for spec in first_tools)


async def test_agent_empty_search_is_insufficient() -> None:
    chat = FakeChatModel(
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="should not run",
            markers_used=(1,),
        ),
    )
    result = await run_ask_agent(
        engagement_id=EngagementId("northwind-fy2025"),
        question=Question(text="Anything?"),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(chat=chat, vector_index=InMemoryVectorIndex()),
    )
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer.reason == InsufficientReason.NO_RELEVANT_CHUNKS
    assert not chat.calls


async def test_agent_model_chosen_query_not_raw_question() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await _index(
        vector_index,
        embedder,
        engagement_id=engagement_id,
        path="contracts/a.pdf",
        text="Payment is due within thirty days.",
    )
    scripted_query = "Contoso payment terms thirty days"
    chat = FakeChatModel(
        auto_search=False,
        tool_turns=[
            ToolTurnResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        id="c1",
                        name="search_relevant_chunks",
                        arguments=json.dumps({"query": scripted_query}),
                    ),
                ),
                usage=LlmUsage(),
            ),
            ToolTurnResult(content=None, tool_calls=(), usage=LlmUsage()),
        ],
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="Thirty days [1].",
            markers_used=(1,),
        ),
    )
    result = await run_ask_agent(
        engagement_id=engagement_id,
        question=Question(text="what about the money stuff?"),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(chat=chat, embedder=embedder, vector_index=vector_index),
    )
    assert result.answer.status == AnswerStatus.ANSWERED
    assert scripted_query != "what about the money stuff?"
    assert result.standalone_question == "what about the money stuff?"
    assert len(chat.tool_turn_calls) >= 1


async def test_agent_max_rounds_stops_tool_loop() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    forever = ToolTurnResult(
        content=None,
        tool_calls=(
            ToolCall(
                id="loop",
                name="search_relevant_chunks",
                arguments=json.dumps({"query": "x"}),
            ),
        ),
        usage=LlmUsage(),
    )
    chat = FakeChatModel(
        auto_search=False,
        tool_turns=[forever, forever, forever, forever],
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="ok [1].",
            markers_used=(1,),
        ),
    )
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await _index(
        vector_index,
        embedder,
        engagement_id=engagement_id,
        path="a.pdf",
        text="ok text",
    )
    result = await run_ask_agent(
        engagement_id=engagement_id,
        question=Question(text="q"),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(
            chat=chat,
            embedder=embedder,
            vector_index=vector_index,
            settings=_settings(agent_max_tool_rounds=2),
        ),
    )
    assert result.answer.status == AnswerStatus.ANSWERED
    assert len(chat.tool_turn_calls) == 2


async def test_agent_list_then_read_then_search() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    engagements = InMemoryEngagementRepository()
    from backend.domain.common import utc_now
    from backend.domain.engagement import Engagement

    now = utc_now()
    await engagements.create(Engagement(id=engagement_id, name="N", created_at=now, updated_at=now))
    documents = InMemoryDocumentRepository()
    storage = InMemoryDocumentStorage()
    doc = Document(
        id=DocumentId(uuid.uuid4()),
        engagement_id=engagement_id,
        path=DocumentPath("notes/terms.md"),
        content_type=ContentType.MARKDOWN,
        size_bytes=20,
        sha256="a" * 64,
        version=1,
        searchable=True,
        created_at=now,
        updated_at=now,
    )
    await documents.upsert(doc)
    await storage.put(engagement_id, doc.path, b"Net thirty days payment term.")

    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await _index(
        vector_index,
        embedder,
        engagement_id=engagement_id,
        path="notes/terms.md",
        text="Net thirty days payment term.",
    )

    chat = FakeChatModel(
        auto_search=False,
        tool_turns=[
            ToolTurnResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        id="t1",
                        name="list_documents",
                        arguments=json.dumps({"prefix": "notes", "depth": 1}),
                    ),
                ),
                usage=LlmUsage(),
            ),
            ToolTurnResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        id="t2",
                        name="read_document",
                        arguments=json.dumps({"path": "notes/terms.md"}),
                    ),
                ),
                usage=LlmUsage(),
            ),
            ToolTurnResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        id="t3",
                        name="search_relevant_chunks",
                        arguments=json.dumps({"query": "payment term"}),
                    ),
                ),
                usage=LlmUsage(),
            ),
            ToolTurnResult(content=None, tool_calls=(), usage=LlmUsage()),
        ],
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="Net thirty [1].",
            markers_used=(1,),
        ),
    )
    result = await run_ask_agent(
        engagement_id=engagement_id,
        question=Question(text="payment terms?"),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(
            chat=chat,
            embedder=embedder,
            vector_index=vector_index,
            engagements=engagements,
            documents=documents,
            storage=storage,
        ),
    )
    assert result.answer.status == AnswerStatus.ANSWERED
    assert len(chat.tool_turn_calls) >= 3
