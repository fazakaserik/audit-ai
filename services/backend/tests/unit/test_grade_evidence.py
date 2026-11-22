"""Unit test: empty retrieval skips LLM generation."""

from __future__ import annotations

from backend.config import Settings
from backend.rag.nodes import AskGraphDeps, grade_evidence, retrieve, route_after_retrieve
from backend.rag.state import AskState
from domain.answer import InsufficientReason, Question
from domain.engagement import EngagementId
from support.fakes import FakeChatModel, FakeEmbedder, InMemoryVectorIndex


async def test_empty_retrieval_routes_to_suggestions_without_chat() -> None:
    chat = FakeChatModel()
    deps = AskGraphDeps(
        chat=chat,
        embedder=FakeEmbedder(),
        vector_index=InMemoryVectorIndex(),
        settings=Settings(relevance_threshold=0.0),
    )
    state: AskState = {
        "engagement_id": EngagementId("northwind-fy2025"),
        "question": Question(text="What is the warranty period?"),
        "folder_scope": None,
    }
    state = {**state, **(await retrieve(state, deps))}
    assert state.get("insufficient_reason") == InsufficientReason.NO_RELEVANT_PASSAGES
    assert route_after_retrieve(state) == "suggest_client_questions"
    state = {**state, **(await grade_evidence(state, deps))}
    assert chat.calls == []
