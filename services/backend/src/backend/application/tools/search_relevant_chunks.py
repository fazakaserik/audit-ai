"""Agent tool: search indexed chunks via RAG retrieval."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.application.agents.progress import SourceHit
from backend.application.dto import ScoredChunk, ToolSpec
from backend.application.rag.retrieve import retrieve_relevant_chunks
from backend.application.tools.base import (
    ToolContext,
    ToolResult,
    append_evidence_within_budget,
    evidence_indices_for,
    parse_optional_folder_prefix,
    tool_spec_from_model,
)
from backend.domain.document import DocumentId

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
        scored = await retrieve_relevant_chunks(
            query=args.query,
            engagement_id=ctx.engagement_id,
            folder_prefix=folder,
            embedder=ctx.embedder,
            vector_index=ctx.vector_index,
            top_k=ctx.settings.retrieval_top_k,
            min_score=ctx.settings.relevance_threshold,
        )
        if not scored:
            return ToolResult(
                content="No chunks met the relevance threshold for this query.",
                summary=f"search_relevant_chunks(query={args.query!r}) → 0 hits",
            )

        seen_ids = {row.chunk.id for row in ctx.evidence}
        candidates = [row for row in scored if row.chunk.id not in seen_ids]
        added, bag_full = append_evidence_within_budget(ctx, candidates)
        # Pull sibling chunks from hit documents so signature/tail pages (e.g. auditor
        # firm name) enter evidence even when only the opinion page ranked highly.
        expanded: list[ScoredChunk] = []
        if not bag_full:
            expanded = await _expand_sibling_chunks(ctx, scored)
            added.extend(expanded)
        if ctx.progress is not None:
            await ctx.progress.sources(
                [SourceHit(path=row.document_path, score=row.score) for row in scored]
            )

        # Only rows actually in the bag — never fall back to `scored` when the bag
        # rejected adds (zip(..., strict=True) would raise on missing indices).
        display = added
        snippet_chars = ctx.settings.agent_search_snippet_chars
        lines: list[str] = [
            f"Found {len(scored)} chunk(s); added {len(added)} to evidence"
            f" ({len(expanded)} sibling expansions"
            + ("; evidence bag at AGENT_EVIDENCE_MAX_CHARS" if bag_full else "")
            + ")."
        ]
        if display:
            indices = evidence_indices_for(ctx.evidence, display)
            for index, row in zip(indices, display, strict=True):
                text = row.chunk.text
                snippet = (
                    text if len(text) <= snippet_chars else text[:snippet_chars].rstrip() + "…"
                )
                page = f" p.{row.chunk.page}" if row.chunk.page is not None else ""
                lines.append(
                    f"- evidence[{index}] {row.document_path}{page} score={row.score:.3f}:\n{snippet}"
                )
        summary = (
            f"search_relevant_chunks(query={args.query!r}) → {len(scored)} hits"
            f" (+{len(expanded)} siblings)"
        )
        return ToolResult(content="\n".join(lines), summary=summary)


async def _expand_sibling_chunks(
    ctx: ToolContext,
    scored: list[ScoredChunk],
) -> list[ScoredChunk]:
    """Add other indexed chunks from documents that already hit search."""
    doc_ids: list[DocumentId] = []
    seen_docs: set[DocumentId] = set()
    for row in scored:
        doc_id = row.chunk.document_id
        if doc_id not in seen_docs:
            seen_docs.add(doc_id)
            doc_ids.append(doc_id)

    candidates: list[ScoredChunk] = []
    for doc_id in doc_ids:
        siblings = await ctx.vector_index.list_document_chunks(
            engagement_id=ctx.engagement_id,
            document_id=doc_id,
        )
        candidates.extend(siblings)
    added, _truncated = append_evidence_within_budget(
        ctx,
        candidates,
        per_call_max_chars=ctx.settings.agent_read_max_chars,
    )
    return added
