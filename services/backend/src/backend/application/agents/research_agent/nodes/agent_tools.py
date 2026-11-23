"""Agent and tool execution nodes."""

from __future__ import annotations

from backend.application.agents.research_agent.state import State
from backend.application.dto import ChatMessage
from backend.application.tools import dispatch_tool, specs_for_names

from ._helpers import thinking_callbacks
from .context import TOOL_NAMES, NodeContext


def make_agent_node(ctx: NodeContext):
    async def agent_node(state: State) -> dict[str, object]:
        turn = await ctx.chat.complete_tool_turn(
            state["messages"],
            specs_for_names(TOOL_NAMES),
            thinking=thinking_callbacks(ctx.chat, ctx.progress),
        )
        usage = state["usage"] + turn.usage
        rounds = state["tool_rounds"] + 1
        if not turn.tool_calls:
            return {
                "pending_tool_calls": (),
                "tool_rounds": rounds,
                "usage": usage,
            }

        messages = list(state["messages"])
        messages.append(
            ChatMessage(
                role="assistant",
                content=turn.content,
                tool_calls=turn.tool_calls,
            )
        )
        return {
            "messages": messages,
            "pending_tool_calls": turn.tool_calls,
            "tool_rounds": rounds,
            "usage": usage,
        }

    return agent_node


def make_tools_node(ctx: NodeContext):
    async def tools_node(state: State) -> dict[str, object]:
        if ctx.progress is not None:
            await ctx.progress.stage("tool")

        messages = list(state["messages"])
        for call in state["pending_tool_calls"]:
            if ctx.progress is not None:
                await ctx.progress.tool_call(name=call.name, arguments=call.arguments)
            result = await dispatch_tool(ctx.tool_ctx, call)
            if ctx.progress is not None:
                await ctx.progress.tool_result(name=call.name, summary=result.summary)
            messages.append(
                ChatMessage(
                    role="tool",
                    content=result.content,
                    tool_call_id=call.id,
                    name=call.name,
                )
            )
        return {
            "messages": messages,
            "pending_tool_calls": (),
        }

    return tools_node
