"""Map application tool specs to OpenAI/Ollama function-tool payloads."""

from __future__ import annotations

from collections.abc import Sequence

from backend.application.dto import ToolSpec


def to_vendor_function_tools(tools: Sequence[ToolSpec]) -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]
