"""Empty retrieval yields insufficient evidence (no generate)."""

from __future__ import annotations

from backend.application.agents.research_agent.graph import GraphDeps, run_graph
from backend.application.agents.research_agent.prompts import AnswerGenerationResult
from backend.config import Settings
from backend.domain.answer import AnswerStatus, InsufficientReason, Question
from backend.domain.engagement import EngagementId
from support.fakes import (
    FakeChatModel,
    FakeEmbedder,
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
    InMemoryEngagementRepository,
    InMemoryVectorIndex,
    agent_search_tool_turns,
)


async def test_empty_index_is_insufficient_without_generation() -> None:
    chat = FakeChatModel(
        tool_turns=agent_search_tool_turns(),
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="should not appear [1]",
            markers_used=(1,),
        ),
    )
    result = await run_graph(
        engagement_id=EngagementId("northwind-fy2025"),
        question=Question(text="What is the payment term?"),
        folder_scope=None,
        prior_turns=(),
        deps=GraphDeps(
            chat=chat,
            embedder=FakeEmbedder(),
            vector_index=InMemoryVectorIndex(),
            engagements=InMemoryEngagementRepository(),
            documents=InMemoryDocumentRepository(),
            storage=InMemoryDocumentStorage(),
            settings=Settings(relevance_threshold=0.0),
        ),
    )
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer.reason == InsufficientReason.NO_RELEVANT_CHUNKS
    assert chat.calls == []
