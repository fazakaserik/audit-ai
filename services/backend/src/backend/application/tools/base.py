"""Shared tool protocol and execution context."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel, TypeAdapter

from backend.application.agents.progress import AskProgress
from backend.application.dto import (
    ScoredChunk,
    ToolSpec,
)
from backend.application.llm.embedder import Embedder
from backend.application.repositories.document import DocumentRepository
from backend.application.repositories.engagement import EngagementRepository
from backend.application.storage.document_storage import DocumentStorage
from backend.application.storage.vector_index import VectorIndex
from backend.config import Settings
from backend.domain.document import FolderPath
from backend.domain.engagement import EngagementId

_FOLDER_PATH = TypeAdapter(FolderPath)


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
    # Non-document tool outputs (e.g. get_current_time) used for grading/generation.
    tool_facts: list[str] = field(default_factory=list)


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


def parse_optional_folder_prefix(raw: str | None) -> FolderPath | None:
    """Map LLM folder prefixes to FolderPath; treat /, '', and blanks as root."""
    if raw is None:
        return None
    stripped = raw.strip().strip("/")
    if not stripped:
        return None
    return _FOLDER_PATH.validate_python(stripped)


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


def evidence_char_total(evidence: Sequence[ScoredChunk]) -> int:
    return sum(len(row.chunk.text) for row in evidence)


def append_evidence_within_budget(
    ctx: ToolContext,
    rows: Sequence[ScoredChunk],
    *,
    per_call_max_chars: int | None = None,
) -> tuple[list[ScoredChunk], bool]:
    """Append unique rows until the evidence-bag (and optional per-call) ceiling is hit.

    Always allows the first new row so a single oversized chunk can still enter the bag.
    Returns ``(added, truncated)``.
    """
    ceiling = ctx.settings.agent_evidence_max_chars
    used = evidence_char_total(ctx.evidence)
    call_used = 0
    seen = {row.chunk.id for row in ctx.evidence}
    added: list[ScoredChunk] = []
    truncated = False
    for row in rows:
        if row.chunk.id in seen:
            continue
        chunk_len = len(row.chunk.text)
        over_bag = used + chunk_len > ceiling
        over_call = (
            per_call_max_chars is not None and call_used + chunk_len > per_call_max_chars
        )
        if added and (over_bag or over_call):
            truncated = True
            break
        if not added and used >= ceiling:
            truncated = True
            break
        ctx.evidence.append(row)
        added.append(row)
        seen.add(row.chunk.id)
        used += chunk_len
        call_used += chunk_len
    return added, truncated
