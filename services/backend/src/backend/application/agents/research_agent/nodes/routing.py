"""Conditional edges for the research agent StateGraph."""

from __future__ import annotations

from typing import Literal

from backend.application.agents.research_agent.state import State

AfterAgent = Literal["tools", "grade_evidence"]
AfterTools = Literal["agent", "grade_evidence"]
AfterGrade = Literal["generate", "__end__"]
AfterGenerate = Literal["finalize", "__end__"]


def route_after_agent(state: State) -> AfterAgent:
    if state["pending_tool_calls"]:
        return "tools"
    return "grade_evidence"


def route_after_tools(state: State, *, max_rounds: int) -> AfterTools:
    if state["tool_rounds"] < max_rounds:
        return "agent"
    return "grade_evidence"


def route_after_grade(state: State) -> AfterGrade:
    if state["answer"] is not None:
        return "__end__"
    return "generate"


def route_after_generate(state: State) -> AfterGenerate:
    if state["answer"] is not None:
        return "__end__"
    return "finalize"
