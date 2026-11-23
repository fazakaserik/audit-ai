"""Ask-agent tools: one module per tool, plus registry helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ValidationError

from backend.application.ports import ToolCall, ToolSpec
from backend.rag.tools.base import Tool, ToolContext, ToolResult
from backend.rag.tools.list_documents import ListDocumentsTool
from backend.rag.tools.read_document import ReadDocumentTool
from backend.rag.tools.search_relevant_chunks import SearchRelevantChunksTool

_TOOLS: tuple[Tool, ...] = (
    SearchRelevantChunksTool(),
    ListDocumentsTool(),
    ReadDocumentTool(),
)
_BY_NAME: Mapping[str, Tool] = {tool.name: tool for tool in _TOOLS}


def all_tools() -> tuple[Tool, ...]:
    return _TOOLS


def tool_specs() -> tuple[ToolSpec, ...]:
    return tuple(tool.spec() for tool in _TOOLS)


def get_tool(name: str) -> Tool | None:
    return _BY_NAME.get(name)


async def dispatch_tool(ctx: ToolContext, call: ToolCall) -> ToolResult:
    tool = get_tool(call.name)
    if tool is None:
        return ToolResult(
            content=f"Unknown tool: {call.name}",
            summary=f"{call.name} → unknown",
        )
    try:
        raw: object = json.loads(call.arguments) if call.arguments.strip() else {}
    except json.JSONDecodeError:
        return ToolResult(
            content=f"Invalid JSON arguments for {call.name}: {call.arguments}",
            summary=f"{call.name} → invalid JSON",
        )
    if not isinstance(raw, dict):
        return ToolResult(
            content=f"Tool arguments must be a JSON object for {call.name}",
            summary=f"{call.name} → invalid args shape",
        )
    try:
        args: BaseModel = tool.args_model.model_validate(raw)
    except ValidationError as exc:
        return ToolResult(
            content=f"Invalid arguments for {call.name}: {exc}",
            summary=f"{call.name} → validation error",
        )
    return await tool.run(ctx, args)


def specs_for_names(names: Sequence[str]) -> tuple[ToolSpec, ...]:
    return tuple(tool.spec() for name in names if (tool := get_tool(name)) is not None)


__all__ = [
    "Tool",
    "ToolContext",
    "ToolResult",
    "all_tools",
    "dispatch_tool",
    "get_tool",
    "tool_specs",
]
