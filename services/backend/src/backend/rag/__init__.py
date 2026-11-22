"""RAG graph and citation helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.rag.citations import filter_and_build_citations
from backend.rag.prompts import AnswerGenerationResult

if TYPE_CHECKING:
    from backend.rag.graph import run_ask_graph
    from backend.rag.nodes import AskGraphDeps

__all__ = [
    "AnswerGenerationResult",
    "AskGraphDeps",
    "filter_and_build_citations",
    "run_ask_graph",
]


def __getattr__(name: str) -> object:
    if name == "run_ask_graph":
        from backend.rag.graph import run_ask_graph

        return run_ask_graph
    if name == "AskGraphDeps":
        from backend.rag.nodes import AskGraphDeps

        return AskGraphDeps
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)