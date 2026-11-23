"""List documents and child folders under an engagement path."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.application.dto import ToolSpec
from backend.application.tools.base import (
    ToolContext,
    ToolResult,
    parse_optional_folder_prefix,
    tool_spec_from_model,
)
from backend.domain.errors import NotFoundError

_CFG = ConfigDict(frozen=True, strict=True, extra="forbid")


class ListDocumentsArgs(BaseModel):
    model_config = _CFG

    prefix: Annotated[str, Field(max_length=1024)] | None = None
    depth: Annotated[int, Field(ge=0, le=20)] | None = 1
    limit: Annotated[int, Field(ge=1, le=100)] = 50


class ListDocumentsTool:
    name = "list_documents"
    description = (
        "Browse the engagement document tree. Returns child folder names and document paths "
        "under an optional prefix. Omit prefix (or use empty) for the engagement root. "
        "Use this to discover where files live before searching."
    )
    args_model = ListDocumentsArgs

    def spec(self) -> ToolSpec:
        return tool_spec_from_model(
            name=self.name,
            description=self.description,
            args_model=self.args_model,
        )

    async def run(self, ctx: ToolContext, args: BaseModel) -> ToolResult:
        if not isinstance(args, ListDocumentsArgs):
            msg = "invalid args for list_documents"
            raise TypeError(msg)
        try:
            prefix = parse_optional_folder_prefix(args.prefix)
        except (ValidationError, ValueError) as exc:
            return ToolResult(
                content=(
                    f"Invalid prefix {args.prefix!r}: {exc}. "
                    "Use a relative folder like 'finance' or omit prefix for root."
                ),
                summary=f"list_documents(prefix={args.prefix!r}) → invalid prefix",
            )
        if prefix is None and ctx.folder_scope is not None:
            prefix = ctx.folder_scope
        engagement = await ctx.engagements.get(ctx.engagement_id)
        if engagement is None:
            raise NotFoundError(f"engagement not found: {ctx.engagement_id}")
        items, folders, total = await ctx.documents.list(
            ctx.engagement_id,
            prefix=prefix,
            depth=args.depth,
            limit=args.limit,
            offset=0,
        )
        lines: list[str] = [
            f"prefix={prefix or '(root)'} total_documents={total}",
        ]
        if folders:
            lines.append("folders: " + ", ".join(folders))
        else:
            lines.append("folders: (none)")
        if items:
            lines.append("documents:")
            for doc in items:
                lines.append(f"- {doc.path} ({doc.content_type})")
        else:
            lines.append("documents: (none)")
        summary = f"list_documents(prefix={prefix!r}) → {len(folders)} folders, {len(items)} docs"
        return ToolResult(content="\n".join(lines), summary=summary)
