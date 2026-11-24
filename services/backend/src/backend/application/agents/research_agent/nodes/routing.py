"""Conditional edges for the research agent StateGraph."""

from __future__ import annotations

from typing import Literal

from backend.application.agents.research_agent.state import State

AfterThink = Literal["tools", "check"]
AfterTools = Literal["think"]
AfterCheck = Literal["think", "__end__"]


def route_after_think(state: State) -> AfterThink:
    if state["pending_tool_calls"]:
        return "tools"
    return "check"


def route_after_tools(_state: State) -> AfterTools:
    return "think"


def route_after_check(state: State) -> AfterCheck:
    if state["answer"] is not None:
        return "__end__"
    return "think"
