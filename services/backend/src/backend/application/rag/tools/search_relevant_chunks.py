"""Hybrid vector/FTS search over engagement chunks."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.application.ports import RetrievalScope, ToolSpec
from backend.application.rag.progress import SourceHit
from backend.application.rag.tools.base import (
    ToolContext,
    ToolResult,
    evidence_indices_for,
    parse_optional_folder_prefix,
    tool_spec_from_model,
)

_CFG = ConfigDict(frozen=True, strict=True, extra="forbid")


class SearchRelevantChunksArgs(BaseModel):
    model_config = _CFG

    query: Annotated[str, Field(min_length=1, max_length=2000)]
    folder_prefix: Annotated[str, Field(max_length=1024)] | None = None


class SearchRelevantChunksTool:
    name = "search_relevant_chunks"
    description = (
        "Search indexed document chunks for this engagement by meaning and exact terms. "
        "Invent a focused search query (identifiers, clause names, amounts). "
        "You may call this multiple times with different queries."
    )
    args_model = SearchRelevantChunksArgs

    def spec(self) -> ToolSpec:
        return tool_spec_from_model(
            name=self.name,
            description=self.description,
            args_model=self.args_model,
        )

    async def run(self, ctx: ToolContext, args: BaseModel) -> ToolResult:
        if not isinstance(args, SearchRelevantChunksArgs):
            msg = "invalid args for search_relevant_chunks"
            raise TypeError(msg)
        folder = ctx.folder_scope
        if args.folder_prefix is not None and args.folder_prefix.strip():
            try:
                parsed = parse_optional_folder_prefix(args.folder_prefix)
            except (ValidationError, ValueError) as exc:
                return ToolResult(
                    content=(
                        f"Invalid folder_prefix {args.folder_prefix!r}: {exc}. "
                        "Use a relative folder like 'finance' or omit folder_prefix."
                    ),
                    summary=(
                        f"search_relevant_chunks(query={args.query!r}) → invalid folder_prefix"
                    ),
                )
            if parsed is not None:
                folder = parsed
        embedded = await ctx.embedder.embed((args.query,))
        scope = RetrievalScope(
            engagement_id=ctx.engagement_id,
            folder_prefix=folder,
            top_k=ctx.settings.retrieval_top_k,
        )
        scored = await ctx.vector_index.search(
            args.query,
            embedded.vectors[0],
            scope,
            embedding_model=ctx.embedder.model_name,
            min_score=ctx.settings.relevance_threshold,
        )
        if not scored:
            return ToolResult(
                content="No chunks met the relevance threshold for this query.",
                summary=f"search_relevant_chunks(query={args.query!r}) → 0 hits",
            )

        seen_ids = {row.chunk.id for row in ctx.evidence}
        added = [row for row in scored if row.chunk.id not in seen_ids]
        ctx.evidence.extend(added)
        if ctx.progress is not None:
            await ctx.progress.sources(
                [SourceHit(path=row.document_path, score=row.score) for row in scored]
            )

        display = added if added else scored
        lines: list[str] = [f"Found {len(scored)} chunk(s); added {len(added)} new to evidence."]
        indices = evidence_indices_for(ctx.evidence, display)
        for index, row in zip(indices, display, strict=True):
            snippet = row.chunk.text[:240].replace("\n", " ")
            page = f" p.{row.chunk.page}" if row.chunk.page is not None else ""
            lines.append(
                f"- evidence[{index}] {row.document_path}{page} score={row.score:.3f}: {snippet}"
            )
        summary = f"search_relevant_chunks(query={args.query!r}) → {len(scored)} hits"
        return ToolResult(content="\n".join(lines), summary=summary)
