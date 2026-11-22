"""Generation declines cleanly when the model cannot answer."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from backend.application.ports import IncompleteStructuredOutputError, ScoredPassage
from backend.config import Settings
from backend.rag.nodes import AskGraphDeps, generate_answer, route_after_generate
from backend.rag.prompts import AnswerGenerationResult
from backend.rag.state import AskState
from domain.answer import InsufficientReason, Question
from domain.document import DocumentId
from domain.engagement import EngagementId
from domain.passage import Passage, PassageId
from support.fakes import FakeChatModel, FakeEmbedder, InMemoryVectorIndex


def _scored() -> list[ScoredPassage]:
    passage = Passage(
        id=PassageId(uuid.uuid4()),
        document_id=DocumentId(uuid.uuid4()),
        document_version=1,
        ordinal=0,
        page=1,
        heading_path=(),
        text="Some policy text.",
        token_count=4,
        created_at=datetime.now(UTC),
    )
    return [
        ScoredPassage(
            passage=passage,
            document_path="policies/a.md",
            score=0.9,
        )
    ]


async def test_model_decline_routes_to_insufficient() -> None:
    chat = FakeChatModel(
        response=AnswerGenerationResult(
            can_answer=False,
            answer_text="",
            decline_reason="The question is not understandable.",
            markers_used=(),
        ),
    )
    deps = AskGraphDeps(
        chat=chat,
        embedder=FakeEmbedder(),
        vector_index=InMemoryVectorIndex(),
        settings=Settings(),
    )
    state: AskState = {
        "engagement_id": EngagementId("northwind-fy2025"),
        "question": Question(text=".."),
        "scored_passages": _scored(),
        "standalone_question": "..",
    }
    state = {**state, **(await generate_answer(state, deps))}
    assert state.get("insufficient_reason") == InsufficientReason.MODEL_JUDGED_INSUFFICIENT
    assert route_after_generate(state) == "suggest_client_questions"
    generation = state["generation"]
    assert generation is not None
    assert generation.can_answer is False
    assert generation.decline_reason == "The question is not understandable."


async def test_incomplete_structured_output_becomes_decline_not_crash() -> None:
    chat = FakeChatModel(error=IncompleteStructuredOutputError("empty content"))
    deps = AskGraphDeps(
        chat=chat,
        embedder=FakeEmbedder(),
        vector_index=InMemoryVectorIndex(),
        settings=Settings(),
    )
    state: AskState = {
        "engagement_id": EngagementId("northwind-fy2025"),
        "question": Question(text=".."),
        "scored_passages": _scored(),
        "standalone_question": "..",
    }
    state = {**state, **(await generate_answer(state, deps))}
    assert state.get("insufficient_reason") == InsufficientReason.MODEL_JUDGED_INSUFFICIENT
    assert route_after_generate(state) == "suggest_client_questions"
    generation = state["generation"]
    assert generation is not None
    assert generation.can_answer is False
    assert generation.decline_reason
