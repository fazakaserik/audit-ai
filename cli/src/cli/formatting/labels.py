"""Human-readable labels for ask-stream stages and tools."""

from __future__ import annotations

TOOL_LABELS: dict[str, str] = {
    "search_relevant_chunks": "Search",
    "read_document": "Read",
    "list_documents": "List",
}

_STAGE_LABELS: dict[str, str] = {
    "think": "Thinking…",
    "tool": "Running tools…",
    "check": "Checking evidence…",
    "suggest": "Suggest client questions…",
    # Legacy stage names (older persisted streams / tests).
    "agent": "Thinking…",
    "generate": "Thinking…",
    "finalize": "Checking evidence…",
    "condense": "Condense question…",
    "retrieve": "Retrieve chunks…",
    "grade": "Grade evidence…",
}


def tool_label(name: str) -> str:
    return TOOL_LABELS.get(name, name)


def stage_label(stage: str) -> str:
    return _STAGE_LABELS.get(stage, stage)
