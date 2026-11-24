"""Unit tests for the tool-calling ask agent."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from backend.application.agents.research_agent.graph import GraphDeps, run_graph
from backend.application.agents.research_agent.prompts import AnswerGenerationResult
from backend.application.dto import (
    ToolCall,
    ToolTurnResult,
)
from backend.config import Settings
from backend.domain.answer import Answered, AnswerStatus, InsufficientReason, Question
from backend.domain.chunk import Chunk, ChunkId
from backend.domain.document import ContentType, Document, DocumentId, DocumentPath
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


def _settings(
    *,
    agent_max_tool_rounds: int = 6,
    agent_max_check_restarts: int = 2,
) -> Settings:
    return Settings(
        relevance_threshold=0.0,
        retrieval_top_k=8,
        agent_max_tool_rounds=agent_max_tool_rounds,
        agent_max_check_restarts=agent_max_check_restarts,
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
) -> GraphDeps:
    return GraphDeps(
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
        tool_turns=agent_search_tool_turns(),
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="Thirty days [1].",
            markers_used=(1,),
        ),
        usage=LlmUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )
    result = await run_graph(
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
        tool_turns=agent_search_tool_turns(),
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="Invented answer [1].",
            markers_used=(1,),
        ),
    )
    result = await run_graph(
        engagement_id=EngagementId("northwind-fy2025"),
        question=Question(text="Anything?"),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(
            chat=chat,
            vector_index=InMemoryVectorIndex(),
            settings=_settings(agent_max_check_restarts=0),
        ),
    )
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer.reason == InsufficientReason.NO_RELEVANT_CHUNKS
    assert not chat.calls


async def test_greeting_answers_without_tools() -> None:
    chat = FakeChatModel(
        auto_search=False,
        tool_turns=[
            ToolTurnResult(
                content="Hi! How can I help with this engagement?", tool_calls=(), usage=LlmUsage()
            ),
        ],
    )
    result = await run_graph(
        engagement_id=EngagementId("northwind-fy2025"),
        question=Question(text="hi"),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(chat=chat),
    )
    assert result.answer.status == AnswerStatus.ANSWERED
    assert result.answer.citations == ()
    assert "Hi" in result.answer.text
    assert len(chat.tool_turn_calls) == 1
    assert chat.tool_turn_calls[0][1]  # tools were offered
    assert not chat.calls


async def test_factual_draft_without_tools_is_rejected() -> None:
    chat = FakeChatModel(
        auto_search=False,
        tool_turns=[
            ToolTurnResult(
                content="Revenue was $5M with no citations.",
                tool_calls=(),
                usage=LlmUsage(),
            ),
        ],
    )
    result = await run_graph(
        engagement_id=EngagementId("northwind-fy2025"),
        question=Question(text="What was Q1 revenue?"),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(chat=chat, settings=_settings(agent_max_check_restarts=0)),
    )
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer.reason == InsufficientReason.NO_RELEVANT_CHUNKS


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
    result = await run_graph(
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
    result = await run_graph(
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
    # Two tool-capable thinks + one forced answer turn after the round cap.
    assert len(chat.tool_turn_calls) == 3
    assert chat.tool_turn_calls[-1][1] == ()


async def test_check_restart_then_grounded_answer() -> None:
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
        auto_search=False,
        tool_turns=[
            # Cited claim with no evidence yet — check fails and restarts think.
            ToolTurnResult(content="Thirty days [1].", tool_calls=(), usage=LlmUsage()),
            ToolTurnResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        id="c1",
                        name="search_relevant_chunks",
                        arguments=json.dumps({"query": "payment terms"}),
                    ),
                ),
                usage=LlmUsage(),
            ),
            ToolTurnResult(content="Thirty days [1].", tool_calls=(), usage=LlmUsage()),
        ],
    )
    result = await run_graph(
        engagement_id=engagement_id,
        question=Question(text="What are the payment terms?"),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(
            chat=chat,
            embedder=embedder,
            vector_index=vector_index,
            settings=_settings(agent_max_check_restarts=2),
        ),
    )
    assert result.answer.status == AnswerStatus.ANSWERED
    assert "[1]" in result.answer.text
    assert len(chat.tool_turn_calls) >= 3


async def test_check_restarts_exhausted_is_insufficient() -> None:
    chat = FakeChatModel(
        auto_search=False,
        tool_turns=[
            ToolTurnResult(content="Still inventing facts [1].", tool_calls=(), usage=LlmUsage()),
            ToolTurnResult(content="Still inventing facts [1].", tool_calls=(), usage=LlmUsage()),
            ToolTurnResult(content="Still inventing facts [1].", tool_calls=(), usage=LlmUsage()),
        ],
    )
    result = await run_graph(
        engagement_id=EngagementId("northwind-fy2025"),
        question=Question(text="What are the payment terms?"),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(chat=chat, settings=_settings(agent_max_check_restarts=1)),
    )
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer.reason == InsufficientReason.NO_RELEVANT_CHUNKS


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
    result = await run_graph(
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


async def test_agent_current_time_answers_without_chunks() -> None:
    chat = FakeChatModel(
        tool_turns=[
            ToolTurnResult(
                content=None,
                tool_calls=(ToolCall(id="t_time", name="get_current_time", arguments="{}"),),
                usage=LlmUsage(),
            ),
            ToolTurnResult(content=None, tool_calls=(), usage=LlmUsage()),
        ],
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="Today is Monday, 23 November 2026 (UTC).",
            markers_used=(),
        ),
    )
    result = await run_graph(
        engagement_id=EngagementId("northwind-fy2025"),
        question=Question(text="What is today's date?"),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(chat=chat),
    )
    assert result.answer.status == AnswerStatus.ANSWERED
    assert result.answer.citations == ()
    assert "2026" in result.answer.text
    assert not chat.calls  # think drafts the answer; no separate generate call


async def test_agent_read_pdf_loads_indexed_chunks_into_evidence() -> None:
    from backend.domain.common import utc_now
    from backend.domain.engagement import Engagement

    engagement_id = EngagementId("fourig-fy2024")
    now = utc_now()
    engagements = InMemoryEngagementRepository()
    await engagements.create(
        Engagement(id=engagement_id, name="4iG", created_at=now, updated_at=now)
    )
    documents = InMemoryDocumentRepository()
    doc_id = DocumentId(uuid.uuid4())
    path = DocumentPath("reports/AGENDA_2_KVJ_4iG_VMT_20240630_signed_EN.pdf")
    await documents.upsert(
        Document(
            id=doc_id,
            engagement_id=engagement_id,
            path=path,
            content_type=ContentType.PDF,
            size_bytes=100,
            sha256="b" * 64,
            version=1,
            searchable=True,
            created_at=now,
            updated_at=now,
        )
    )
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    auditor_text = (
        "Quercus Audit Kft. Veszprém, Radnóti tér 2/c. "
        "Licence number 002651. Tölgyes András registered auditor."
    )
    chunk = Chunk(
        id=ChunkId(uuid.uuid4()),
        document_id=doc_id,
        document_version=1,
        ordinal=0,
        page=3,
        heading_path=(),
        text=auditor_text,
        token_count=max(1, len(auditor_text.split())),
        created_at=now,
    )
    embedded = await embedder.embed((auditor_text,))
    await vector_index.upsert_chunks(
        engagement_id=engagement_id,
        document_id=doc_id,
        document_path=path,
        document_version=1,
        chunks=(chunk,),
        embeddings=(embedded.vectors[0],),
        embedding_model=embedder.model_name,
    )
    chat = FakeChatModel(
        auto_search=False,
        tool_turns=[
            ToolTurnResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        id="t_read",
                        name="read_document",
                        arguments=json.dumps({"path": str(path)}),
                    ),
                ),
                usage=LlmUsage(),
            ),
            ToolTurnResult(content=None, tool_calls=(), usage=LlmUsage()),
        ],
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="Quercus Audit Kft. audited 4iG [1].",
            markers_used=(1,),
        ),
    )
    result = await run_graph(
        engagement_id=engagement_id,
        question=Question(text="Who audited 4ig?"),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(
            chat=chat,
            embedder=embedder,
            vector_index=vector_index,
            engagements=engagements,
            documents=documents,
        ),
    )
    assert result.answer.status == AnswerStatus.ANSWERED
    assert "Quercus" in result.answer.text
    assert result.answer.citations[0].snippet.startswith("Quercus")


async def test_search_expands_sibling_chunks_from_hit_document() -> None:
    """Opinion-page hits must pull the signature sibling into evidence."""
    engagement_id = EngagementId("fourig-fy2024")
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    doc_id = DocumentId(uuid.uuid4())
    path = "reports/auditor.pdf"
    now = datetime.now(UTC)
    opinion = Chunk(
        id=ChunkId(uuid.uuid4()),
        document_id=doc_id,
        document_version=1,
        ordinal=0,
        page=1,
        heading_path=(),
        text="INDEPENDENT AUDITOR'S REPORT for 4iG Public Limited Company opinion.",
        token_count=10,
        created_at=now,
    )
    signature = Chunk(
        id=ChunkId(uuid.uuid4()),
        document_id=doc_id,
        document_version=1,
        ordinal=1,
        page=3,
        heading_path=(),
        text="Quercus Audit Kft. Tölgyes András registered auditor Licence 005572.",
        token_count=10,
        created_at=now,
    )
    # Embed opinion with query-like text so FakeEmbedder cosine prefers it;
    # signature uses distinct wording so it would miss top_k without expansion.
    emb_opinion = await embedder.embed((opinion.text,))
    emb_signature = await embedder.embed(("zzzz unrelated padding tokens here",))
    await vector_index.upsert_chunks(
        engagement_id=engagement_id,
        document_id=doc_id,
        document_path=path,
        document_version=1,
        chunks=(opinion, signature),
        embeddings=(emb_opinion.vectors[0], emb_signature.vectors[0]),
        embedding_model=embedder.model_name,
    )
    chat = FakeChatModel(
        tool_turns=agent_search_tool_turns(query="4iG independent auditor report"),
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="Quercus Audit Kft. audited 4iG [2].",
            markers_used=(2,),
        ),
    )
    result = await run_graph(
        engagement_id=engagement_id,
        question=Question(text="Who audited 4ig?"),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(
            chat=chat,
            embedder=embedder,
            vector_index=vector_index,
            # top_k=1 keeps only the opinion hit; siblings must expand in Quercus.
            settings=Settings(relevance_threshold=0.0, retrieval_top_k=1),
        ),
    )
    assert result.answer.status == AnswerStatus.ANSWERED
    assert "Quercus" in result.answer.text


async def test_retry_follow_up_reuses_prior_standalone_question() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await _index(
        vector_index,
        embedder,
        engagement_id=engagement_id,
        path="reports/auditor.pdf",
        text="Quercus Audit Kft. audited 4iG Public Limited Company.",
    )
    prior = Turn(
        id=TurnId(uuid.uuid4()),
        session_id=SessionId(uuid.uuid4()),
        ordinal=0,
        question=Question(text="Who audited 4ig?"),
        standalone_question="Who audited 4ig?",
        answer=Answered(text="(insufficient)", citations=()),
        created_at=datetime.now(UTC),
        usage=LlmUsage(),
    )
    chat = FakeChatModel(
        tool_turns=agent_search_tool_turns(),
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="Quercus Audit Kft. [1].",
            markers_used=(1,),
        ),
    )
    result = await run_graph(
        engagement_id=engagement_id,
        question=Question(text="try again"),
        folder_scope=None,
        prior_turns=(prior,),
        deps=_deps(chat=chat, embedder=embedder, vector_index=vector_index),
    )
    assert result.standalone_question == "Who audited 4ig?"
    assert result.answer.status == AnswerStatus.ANSWERED


async def test_agent_uncited_draft_with_evidence_is_rejected() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await _index(
        vector_index,
        embedder,
        engagement_id=engagement_id,
        path="reports/auditor.pdf",
        text="Quercus Audit Kft. issued the independent auditor's report.",
    )
    chat = FakeChatModel(
        tool_turns=agent_search_tool_turns(),
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="Quercus Audit Kft. audited the company.",
            markers_used=(1,),
        ),
        # markers_used on structured responses is unused by check; drafts need inline [n].
    )
    result = await run_graph(
        engagement_id=engagement_id,
        question=Question(text="Who audited them?"),
        folder_scope=None,
        prior_turns=(),
        deps=_deps(
            chat=chat,
            embedder=embedder,
            vector_index=vector_index,
            settings=_settings(agent_max_check_restarts=0),
        ),
    )
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
