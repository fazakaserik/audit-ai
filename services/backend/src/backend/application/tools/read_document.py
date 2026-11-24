"""Read a document into the evidence bag (text files or indexed PDF/Office chunks)."""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from backend.application.dto import (
    ScoredChunk,
    ToolSpec,
)
from backend.application.tools.base import (
    ToolContext,
    ToolResult,
    append_evidence_within_budget,
    evidence_char_total,
    evidence_indices_for,
    tool_spec_from_model,
)
from backend.domain.chunk import Chunk, ChunkId
from backend.domain.common import utc_now
from backend.domain.document import ContentType, DocumentId, DocumentPath
from backend.domain.errors import NotFoundError

_DOCUMENT_PATH = TypeAdapter(DocumentPath)

_CFG = ConfigDict(frozen=True, strict=True, extra="forbid")

_INDEXED_CONTENT_TYPES: frozenset[ContentType] = frozenset(
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
        "Load a document into evidence. For markdown/text/HTML/CSV, reads file text. "
        "For PDFs and Office files (DOCX, XLSX, PPTX), loads the indexed page/section "
        "chunks for that path so you can cite them. Prefer this after search finds a "
        "relevant file and you need more of its content."
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
        except Exception as exc:
            return ToolResult(
                content=f"Failed to read document {path}: {exc}",
                summary=f"read_document(path={path!r}) → error",
            )

        if document.content_type in _INDEXED_CONTENT_TYPES:
            return await _load_indexed_chunks(
                ctx,
                path=path,
                document_id=document.id,
            )

        try:
            data = await ctx.storage.get(ctx.engagement_id, path)
        except Exception as exc:
            return ToolResult(
                content=f"Failed to read document {path}: {exc}",
                summary=f"read_document(path={path!r}) → error",
            )

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return ToolResult(
                content=f"{path} could not be decoded as UTF-8 text.",
                summary=f"read_document(path={path!r}) → decode error",
            )

        bag_used = evidence_char_total(ctx.evidence)
        bag_room = ctx.settings.agent_evidence_max_chars - bag_used
        if bag_room <= 0:
            return ToolResult(
                content=(
                    f"Evidence bag is at AGENT_EVIDENCE_MAX_CHARS "
                    f"({ctx.settings.agent_evidence_max_chars}); cannot load {path}."
                ),
                summary=f"read_document(path={path!r}) → evidence bag full",
            )
        max_chars = min(ctx.settings.agent_read_max_chars, bag_room)
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
        append_evidence_within_budget(ctx, (scored,))
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


async def _load_indexed_chunks(
    ctx: ToolContext,
    *,
    path: DocumentPath,
    document_id: DocumentId,
) -> ToolResult:
    indexed = await ctx.vector_index.list_document_chunks(
        engagement_id=ctx.engagement_id,
        document_id=document_id,
    )
    if not indexed:
        return ToolResult(
            content=(
                f"{path} has no indexed chunks yet (still processing or empty). "
                "Call search_relevant_chunks with identifiers from the question, "
                "or wait for indexing to finish."
            ),
            summary=f"read_document(path={path!r}) → not indexed",
        )

    added, truncated = append_evidence_within_budget(
        ctx,
        indexed,
        per_call_max_chars=ctx.settings.agent_read_max_chars,
    )

    if not added:
        existing = [row for row in ctx.evidence if row.document_path == path]
        indices = evidence_indices_for(ctx.evidence, existing)
        index_list = ", ".join(f"evidence[{i}]" for i in indices) or "(none)"
        if existing:
            return ToolResult(
                content=f"{path} chunks are already in evidence: {index_list}.",
                summary=f"read_document(path={path!r}) → already in evidence",
            )
        return ToolResult(
            content=(
                f"Evidence bag is at AGENT_EVIDENCE_MAX_CHARS "
                f"({ctx.settings.agent_evidence_max_chars}); cannot load more of {path}."
            ),
            summary=f"read_document(path={path!r}) → evidence bag full",
        )

    used_chars = sum(len(row.chunk.text) for row in added)
    indices = evidence_indices_for(ctx.evidence, added)
    lines: list[str] = [
        f"Loaded {len(added)} indexed chunk(s) from {path} into evidence"
        f" ({used_chars} chars"
        + ("; truncated to agent_read_max_chars / AGENT_EVIDENCE_MAX_CHARS" if truncated else "")
        + ")."
    ]
    for index, row in zip(indices, added, strict=True):
        snippet = row.chunk.text[:500].replace("\n", " ")
        page = f" p.{row.chunk.page}" if row.chunk.page is not None else ""
        lines.append(f"- evidence[{index}]{page}: {snippet}")
    return ToolResult(
        content="\n".join(lines),
        summary=f"read_document(path={path!r}) → {len(added)} chunks",
    )
