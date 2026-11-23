"""Research agent entrypoints (delegates to the LangGraph pipeline)."""

from __future__ import annotations

from collections.abc import Sequence

from backend.application.agents.research_agent.graph import GraphDeps, GraphResult, run_graph
from backend.domain.answer import Question
from backend.domain.document import FolderPath
from backend.domain.engagement import EngagementId
from backend.domain.session import Turn

AgentDeps = GraphDeps
AgentResult = GraphResult


async def run_agent(
    *,
    engagement_id: EngagementId,
    question: Question,
    folder_scope: FolderPath | None,
    prior_turns: Sequence[Turn],
    deps: AgentDeps,
) -> AgentResult:
    return await run_graph(
        engagement_id=engagement_id,
        question=question,
        folder_scope=folder_scope,
        prior_turns=prior_turns,
        deps=deps,
    )
