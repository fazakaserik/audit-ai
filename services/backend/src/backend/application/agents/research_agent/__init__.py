"""Research agent: LangGraph evidence-gathering pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.agents.research_agent.citations import filter_and_build_citations
from backend.application.agents.research_agent.prompts import AnswerGenerationResult

if TYPE_CHECKING:
    from backend.application.agents.research_agent.graph import GraphDeps, run_graph

__all__ = [
    "AnswerGenerationResult",
    "GraphDeps",
    "filter_and_build_citations",
    "run_graph",
]


def __getattr__(name: str) -> object:
    if name == "run_graph":
        from backend.application.agents.research_agent.graph import run_graph

        return run_graph
    if name == "GraphDeps":
        from backend.application.agents.research_agent.graph import GraphDeps

        return GraphDeps
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
