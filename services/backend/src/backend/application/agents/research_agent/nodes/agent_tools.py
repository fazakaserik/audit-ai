"""Think and tool execution nodes."""

from __future__ import annotations

from backend.application.agents.research_agent.state import State
from backend.application.dto import ChatMessage
from backend.application.tools import dispatch_tool, specs_for_names

from ._helpers import thinking_callbacks
from .context import TOOL_NAMES, NodeContext


def make_think_node(ctx: NodeContext):
    max_rounds = ctx.settings.agent_max_tool_rounds

    async def think_node(state: State) -> dict[str, object]:
        if ctx.progress is not None:
            await ctx.progress.stage("think")

        allow_tools = state["tool_rounds"] < max_rounds
        tool_specs = specs_for_names(TOOL_NAMES) if allow_tools else ()
        turn = await ctx.chat.complete_tool_turn(
            state["messages"],
            tool_specs,
            thinking=thinking_callbacks(ctx.chat, ctx.progress),
        )
        usage = state["usage"] + turn.usage
        rounds = state["tool_rounds"] + (1 if allow_tools else 0)

        if allow_tools and turn.tool_calls:
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
                "draft_answer": None,
                "usage": usage,
            }

        draft = (turn.content or "").strip() or None
        messages = list(state["messages"])
        if draft:
            messages.append(ChatMessage(role="assistant", content=draft))
        return {
            "messages": messages,
            "pending_tool_calls": (),
            "tool_rounds": rounds,
            "draft_answer": draft,
            "usage": usage,
        }

    return think_node


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
