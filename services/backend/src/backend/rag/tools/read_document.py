"""Read a text/markdown document into the evidence bag (PDFs: use search)."""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from backend.application.get_document import get_document
from backend.application.ports import ScoredChunk, ToolSpec
from backend.rag.tools.base import ToolContext, ToolResult, tool_spec_from_model
from domain.chunk import Chunk, ChunkId
from domain.common import utc_now
from domain.document import ContentType, DocumentPath

_DOCUMENT_PATH = TypeAdapter(DocumentPath)

_CFG = ConfigDict(frozen=True, strict=True, extra="forbid")


class ReadDocumentArgs(BaseModel):
    model_config = _CFG

    path: Annotated[str, Field(min_length=1, max_length=1024)]


class ReadDocumentTool:
    name = "read_document"
    description = (
        "Read the full text of a markdown or plain-text document into evidence. "
        "For PDFs, prefer search_relevant_chunks with targeted queries instead."
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
            result = await get_document(
                ctx.engagements,
                ctx.documents,
                ctx.storage,
                engagement_id=ctx.engagement_id,
                path=path,
            )
        except Exception as exc:
            return ToolResult(
                content=f"Failed to read document {path}: {exc}",
                summary=f"read_document(path={path!r}) → error",
            )

        content_type = result.document.content_type
        if content_type == ContentType.PDF:
            return ToolResult(
                content=(
                    f"{path} is a PDF. Do not dump binary content. "
                    "Call search_relevant_chunks with identifiers or phrases from the question."
                ),
                summary=f"read_document(path={path!r}) → pdf (use search)",
            )

        try:
            text = result.data.decode("utf-8")
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
            document_id=result.document.id,
            document_version=result.document.version,
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
