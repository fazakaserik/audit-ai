"""Read a text/markdown document into the evidence bag (PDFs: use search)."""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from backend.application.dto import (
    ScoredChunk,
    ToolSpec,
)
from backend.application.tools.base import ToolContext, ToolResult, tool_spec_from_model
from backend.domain.chunk import Chunk, ChunkId
from backend.domain.common import utc_now
from backend.domain.document import ContentType, DocumentPath
from backend.domain.errors import NotFoundError

_DOCUMENT_PATH = TypeAdapter(DocumentPath)

_CFG = ConfigDict(frozen=True, strict=True, extra="forbid")

_BINARY_CONTENT_TYPES: frozenset[ContentType] = frozenset(
    {
        ContentType.PDF,
        ContentType.DOCX,
        ContentType.XLSX,
        ContentType.PPTX,
    },
)


class ReadDocumentArgs(BaseModel):
    model_config = _CFG

    path: Annotated[str, Field(min_length=1, max_length=1024)]


class ReadDocumentTool:
    name = "read_document"
    description = (
        "Read the full text of a markdown, plain-text, HTML, or CSV document "
        "into evidence. For PDFs and Office files (DOCX, XLSX, PPTX), prefer "
        "search_relevant_chunks with targeted queries instead."
    )
    args_model = ReadDocumentArgs

    def spec(self) -> ToolSpec:
        return tool_spec_from_model(
            name=self.name,
            description=self.description,
            args_model=self.args_model,
        )

    async def run(self, ctx: ToolContext, args: BaseModel) -> ToolResult:
        if not isinstance(args, ReadDocumentArgs):
            msg = "invalid args for read_document"
            raise TypeError(msg)
        path = _DOCUMENT_PATH.validate_python(args.path.strip())
        try:
            engagement = await ctx.engagements.get(ctx.engagement_id)
            if engagement is None:
                raise NotFoundError(f"engagement not found: {ctx.engagement_id}")
            document = await ctx.documents.get_by_path(ctx.engagement_id, path)
            if document is None:
                raise NotFoundError(f"document not found: {path}")
            data = await ctx.storage.get(ctx.engagement_id, path)
        except Exception as exc:
            return ToolResult(
                content=f"Failed to read document {path}: {exc}",
                summary=f"read_document(path={path!r}) → error",
            )

        content_type = document.content_type
        if content_type in _BINARY_CONTENT_TYPES:
            label = content_type.value.upper()
            return ToolResult(
                content=(
                    f"{path} is a {label} file. Do not dump binary content. "
                    "Call search_relevant_chunks with identifiers or phrases from the question."
                ),
                summary=f"read_document(path={path!r}) → {content_type.value} (use search)",
            )

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return ToolResult(
                content=f"{path} could not be decoded as UTF-8 text.",
                summary=f"read_document(path={path!r}) → decode error",
            )

        max_chars = ctx.settings.agent_read_max_chars
        truncated = text[:max_chars]
        if len(text) > max_chars:
            truncated = truncated.rstrip() + "\n…[truncated]"

        if not truncated.strip():
            return ToolResult(
                content=f"{path} is empty.",
                summary=f"read_document(path={path!r}) → empty",
            )

        chunk = Chunk(
            id=ChunkId(uuid.uuid4()),
            document_id=document.id,
            document_version=document.version,
            ordinal=0,
            page=None,
            heading_path=(),
            text=truncated,
            token_count=max(1, len(truncated.split())),
            created_at=utc_now(),
        )
        scored = ScoredChunk(chunk=chunk, document_path=path, score=1.0)
        ctx.evidence.append(scored)
        evidence_index = len(ctx.evidence)
        preview = truncated[:240].replace("\n", " ")
        content = (
            f"Loaded {path} into evidence[{evidence_index}] "
            f"({len(truncated)} chars).\nPreview: {preview}"
        )
        return ToolResult(
            content=content,
            summary=f"read_document(path={path!r}) → evidence[{evidence_index}]",
        )
