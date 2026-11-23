"""List documents and child folders under an engagement path."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from backend.application.list_documents import list_documents
from backend.application.ports import ToolSpec
from backend.rag.tools.base import ToolContext, ToolResult, tool_spec_from_model
from domain.document import FolderPath

_FOLDER_PATH = TypeAdapter(FolderPath)

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
        "under an optional prefix. Use this to discover where files live before searching."
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
        prefix: FolderPath | None = None
        if args.prefix is not None and args.prefix.strip():
            prefix = _FOLDER_PATH.validate_python(args.prefix.strip())
        elif ctx.folder_scope is not None:
            prefix = ctx.folder_scope
        result = await list_documents(
            ctx.engagements,
            ctx.documents,
            engagement_id=ctx.engagement_id,
            prefix=prefix,
            depth=args.depth,
            limit=args.limit,
            offset=0,
        )
        lines: list[str] = [
            f"prefix={prefix or '(root)'} total_documents={result.total}",
        ]
        if result.folders:
            lines.append("folders: " + ", ".join(result.folders))
        else:
            lines.append("folders: (none)")
        if result.items:
            lines.append("documents:")
            for doc in result.items:
                lines.append(f"- {doc.path} ({doc.content_type})")
        else:
            lines.append("documents: (none)")
        summary = (
            f"list_documents(prefix={prefix!r}) → "
            f"{len(result.folders)} folders, {len(result.items)} docs"
        )
        return ToolResult(content="\n".join(lines), summary=summary)
