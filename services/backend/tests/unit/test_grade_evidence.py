"""Empty retrieval fails the evidence check (ungrounded draft)."""

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


async def test_empty_index_is_insufficient_after_check() -> None:
    chat = FakeChatModel(
        tool_turns=agent_search_tool_turns(),
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="Payment is thirty days [1].",
            markers_used=(1,),
        ),
        # No retries so a single failed check ends the run.
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
            settings=Settings(relevance_threshold=0.0, agent_max_check_restarts=0),
        ),
    )
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer.reason == InsufficientReason.NO_RELEVANT_CHUNKS
    assert chat.calls == []
