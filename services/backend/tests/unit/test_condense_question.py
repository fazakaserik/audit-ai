"""Unit tests: condense_question rewrites follow-ups; evidence stays in retrieval only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from backend.config import Settings
from backend.rag.graph import run_ask_graph
from backend.rag.nodes import AskGraphDeps, condense_question
from backend.rag.prompts import AnswerGenerationResult, CondenseQuestionResult
from backend.rag.state import AskState
from domain.answer import Answered, Citation, Question
from domain.common import new_uuid, utc_now
from domain.document import DocumentId
from domain.engagement import EngagementId
from domain.passage import Passage, PassageId
from domain.session import SessionId, Turn, TurnId
from support.fakes import FakeChatModel, FakeEmbedder, InMemoryVectorIndex


async def test_condense_skips_model_without_prior_turns() -> None:
    chat = FakeChatModel(
        response=CondenseQuestionResult(standalone_question="should not be used"),
    )
    deps = AskGraphDeps(
        chat=chat,
        embedder=FakeEmbedder(),
        vector_index=InMemoryVectorIndex(),
        settings=Settings(),
    )
    state: AskState = {
        "question": Question(text="What are payment terms?"),
        "prior_turns": (),
    }
    update = await condense_question(state, deps)
    assert update["standalone_question"] == "What are payment terms?"
    assert chat.calls == []


async def test_condense_uses_chat_when_prior_turns_exist() -> None:
    chat = FakeChatModel(
        response=CondenseQuestionResult(
            standalone_question="What is the Contoso payment period in days?",
        ),
    )
    deps = AskGraphDeps(
        chat=chat,
        embedder=FakeEmbedder(),
        vector_index=InMemoryVectorIndex(),
        settings=Settings(session_context_turns=5),
    )
    prior = Turn(
        id=TurnId(new_uuid()),
        session_id=SessionId(new_uuid()),
        ordinal=0,
        question=Question(text="Tell me about Contoso."),
        standalone_question="What does the Contoso contract cover?",
        answer=Answered(
            text="Contoso requires payment within thirty days [1].",
            citations=(
                Citation(
                    marker=1,
                    passage_id=PassageId(new_uuid()),
                    document_id=DocumentId(uuid.uuid4()),
                    document_path="contracts/contoso.pdf",
                    page=1,
                    heading_path=(),
                    snippet="thirty days",
                    score=0.9,
                ),
            ),
        ),
        created_at=utc_now(),
    )
    state: AskState = {
        "question": Question(text="And the exact period?"),
        "prior_turns": (prior,),
    }
    update = await condense_question(state, deps)
    assert update["standalone_question"] == "What is the Contoso payment period in days?"
    assert len(chat.calls) == 1
    _, schema = chat.calls[0]
    assert schema is CondenseQuestionResult
    user_content = chat.calls[0][0][1].content
    assert "prior answer omitted" in user_content
    assert "thirty days" not in user_content


async def test_follow_up_retrieval_uses_condensed_query_not_prior_answer() -> None:
    passage_text = "Net payment terms are thirty calendar days from invoice date."
    embedder = FakeEmbedder()
    embedded = await embedder.embed((passage_text,))
    vector_index = InMemoryVectorIndex()
    engagement_id = EngagementId("northwind-fy2025")
    doc_id = DocumentId(uuid.uuid4())
    passage = Passage(
        id=PassageId(uuid.uuid4()),
        document_id=doc_id,
        document_version=1,
        ordinal=0,
        page=2,
        heading_path=(),
        text=passage_text,
        token_count=12,
        created_at=datetime.now(UTC),
    )
    await vector_index.upsert_passages(
        engagement_id=engagement_id,
        document_id=doc_id,
        document_path="contracts/contoso.pdf",
        document_version=1,
        passages=(passage,),
        embeddings=(embedded.vectors[0],),
        embedding_model=embedder.model_name,
    )

    chat = FakeChatModel(
        responses=[
            CondenseQuestionResult(
                standalone_question=passage_text,
            ),
            AnswerGenerationResult(
                can_answer=True,
                answer_text="Thirty days [1].",
                markers_used=(1,),
            ),
        ],
    )
    deps = AskGraphDeps(
        chat=chat,
        embedder=embedder,
        vector_index=vector_index,
        settings=Settings(relevance_threshold=0.0),
    )
    prior = Turn(
        id=TurnId(new_uuid()),
        session_id=SessionId(new_uuid()),
        ordinal=0,
        question=Question(text="What about Contoso?"),
        standalone_question="Summarize the Contoso contract.",
        answer=Answered(
            text="SECRET PRIOR ANSWER BODY",
            citations=(
                Citation(
                    marker=1,
                    passage_id=PassageId(new_uuid()),
                    document_id=doc_id,
                    document_path="contracts/contoso.pdf",
                    page=1,
                    heading_path=(),
                    snippet="old",
                    score=0.5,
                ),
            ),
        ),
        created_at=utc_now(),
    )
    result = await run_ask_graph(
        engagement_id=engagement_id,
        question=Question(text="How long to pay?"),
        folder_scope=None,
        prior_turns=(prior,),
        deps=deps,
    )
    assert result.standalone_question == passage_text
    assert isinstance(result.answer, Answered)
    gen_call = chat.calls[1]
    user_content = gen_call[0][1].content
    assert "SECRET PRIOR ANSWER BODY" not in user_content
    assert passage_text in user_content
