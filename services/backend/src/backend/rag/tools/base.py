"""Shared tool protocol and execution context."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel

from backend.application.ports import (
    DocumentRepository,
    DocumentStorage,
    Embedder,
    EngagementRepository,
    ScoredChunk,
    ToolSpec,
    VectorIndex,
)
from backend.config import Settings
from backend.rag.progress import AskProgress
from domain.document import FolderPath
from domain.engagement import EngagementId


@dataclass
class ToolContext:
    engagement_id: EngagementId
    folder_scope: FolderPath | None
    embedder: Embedder
    vector_index: VectorIndex
    engagements: EngagementRepository
    documents: DocumentRepository
    storage: DocumentStorage
    settings: Settings
    progress: AskProgress | None = None
    evidence: list[ScoredChunk] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ToolResult:
    content: str
    summary: str


class Tool(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def args_model(self) -> type[BaseModel]: ...

    def spec(self) -> ToolSpec: ...

    async def run(self, ctx: ToolContext, args: BaseModel) -> ToolResult: ...


def tool_spec_from_model(
    *,
    name: str,
    description: str,
    args_model: type[BaseModel],
) -> ToolSpec:
    schema = args_model.model_json_schema()
    parameters: dict[str, object] = {
        "type": "object",
        "properties": schema.get("properties", {}),
        "required": schema.get("required", []),
        "additionalProperties": False,
    }
    return ToolSpec(name=name, description=description, parameters=parameters)


def evidence_indices_for(
    evidence: Sequence[ScoredChunk],
    added: Sequence[ScoredChunk],
) -> list[int]:
    """1-based indices of ``added`` chunks within ``evidence`` (by identity then id)."""
    indices: list[int] = []
    for item in added:
        for index, existing in enumerate(evidence, start=1):
            if existing is item or existing.chunk.id == item.chunk.id:
                indices.append(index)
                break
    return indices
