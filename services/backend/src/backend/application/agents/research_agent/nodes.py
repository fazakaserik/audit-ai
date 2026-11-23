"""LangGraph nodes and routers for the research agent."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, assert_never

from backend.application.agents.progress import AskProgress
from backend.application.agents.research_agent.citations import filter_and_build_citations
from backend.application.agents.research_agent.prompts import (
    AnswerGenerationResult,
    build_generation_messages,
)
from backend.application.agents.research_agent.state import State
from backend.application.dto import (
    ChatMessage,
    IncompleteStructuredOutputError,
    ScoredChunk,
)
from backend.application.llm.chat_model import ChatModel
from backend.application.tools import dispatch_tool, specs_for_names
from backend.application.tools.base import ToolContext
from backend.config import Settings
from backend.domain.answer import (
    Answered,
    Citation,
    InsufficientEvidence,
    InsufficientReason,
    SuggestedClientQuestion,
)

TOOL_NAMES: tuple[str, ...] = (
    "search_relevant_chunks",
    "list_documents",
    "read_document",
    "get_current_time",
)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _topic_phrase(question_text: str) -> str:
    cleaned = " ".join(question_text.split()).strip().rstrip("?.!")
    if not cleaned:
        return "this topic"
    return _truncate(cleaned, 200)


def _as_full_question(text: str) -> str:
    """Normalize to a single full interrogative ending with '?'."""
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return ""
    cleaned = cleaned.rstrip("?.!") + "?"
    return _truncate(cleaned, 500)


def default_client_suggestions(
    question_text: str,
    *,
    reason: InsufficientReason,
    auditor_role: str | None = None,
    topic: str | None = None,
) -> tuple[SuggestedClientQuestion, ...]:
    """Fallback full questions for missing material — never echo a yes/no restatement."""
    phrase = _topic_phrase(question_text)
    role_note = f" Scoped for the {auditor_role} reviewer." if auditor_role else ""
    topic_note = f" Topic focus: {topic}." if topic else ""
    match reason:
        case InsufficientReason.NO_RELEVANT_CHUNKS:
            return (
                SuggestedClientQuestion(
                    question=_as_full_question(f"Which documents define or cover {phrase}"),
                    rationale=(
                        "No indexed chunks met the relevance threshold for this question."
                        f"{role_note}{topic_note}"
                    ),
                ),
            )
        case InsufficientReason.MODEL_JUDGED_INSUFFICIENT:
            return (
                SuggestedClientQuestion(
                    question=_as_full_question(f"What definition or policy clause covers {phrase}"),
                    rationale=(
                        "Retrieved evidence was not enough to ground a confident answer."
                        f"{role_note}{topic_note}"
                    ),
                ),
            )
    assert_never(reason)


def suggestions_from_generation(
    generation: AnswerGenerationResult,
    *,
    question_text: str,
    auditor_role: str | None,
    topic: str | None,
) -> tuple[SuggestedClientQuestion, ...]:
    """Prefer model client questions; fall back to deterministic defaults."""
    cleaned: list[SuggestedClientQuestion] = []
    uncertainties = tuple(
        _truncate(" ".join(item.split()), 500) for item in generation.uncertainties if item.strip()
    )
    rationale_base = (
        uncertainties[0]
        if uncertainties
        else (generation.decline_reason.strip() or "Evidence does not fully support an answer.")
    )
    for raw in generation.client_questions:
        ask = _as_full_question(raw)
        if len(ask) < 2:
            continue
        cleaned.append(SuggestedClientQuestion(question=ask, rationale=rationale_base))
        if len(cleaned) >= 3:
            break
    if cleaned:
        return tuple(cleaned)
    return default_client_suggestions(
        question_text,
        reason=InsufficientReason.MODEL_JUDGED_INSUFFICIENT,
        auditor_role=auditor_role,
        topic=topic,
    )


def uncertainties_from_generation(generation: AnswerGenerationResult) -> tuple[str, ...]:
    items = tuple(
        _truncate(" ".join(item.split()), 500) for item in generation.uncertainties if item.strip()
    )
    if items:
        return items[:5]
    reason = generation.decline_reason.strip()
    if reason:
        return (_truncate(reason, 500),)
    return ()


def _thinking(chat: ChatModel, progress: AskProgress | None):
    if progress is None or not chat.supports_thinking:
        return None
    return progress.thinking_callbacks()


def _insufficient(
    question_text: str,
    *,
    reason: InsufficientReason,
    auditor_role: str | None,
    topic: str | None,
    partial_citations: tuple[Citation, ...] = (),
    uncertainties: tuple[str, ...] = (),
    suggested_client_questions: tuple[SuggestedClientQuestion, ...] | None = None,
) -> InsufficientEvidence:
    suggestions = (
        suggested_client_questions
        if suggested_client_questions is not None
        else default_client_suggestions(
            question_text,
            reason=reason,
            auditor_role=auditor_role,
            topic=topic,
        )
    )
    return InsufficientEvidence(
        reason=reason,
        partial_citations=partial_citations,
        uncertainties=uncertainties,
        suggested_client_questions=suggestions,
    )


AfterAgent = Literal["tools", "grade_evidence"]
AfterTools = Literal["agent", "grade_evidence"]
AfterGrade = Literal["generate", "__end__"]
AfterGenerate = Literal["finalize", "__end__"]


@dataclass(frozen=True, slots=True)
class NodeContext:
    chat: ChatModel
    settings: Settings
    tool_ctx: ToolContext
    progress: AskProgress | None


def make_agent_node(ctx: NodeContext):
    async def agent_node(state: State) -> dict[str, object]:
        turn = await ctx.chat.complete_tool_turn(
            state["messages"],
            specs_for_names(TOOL_NAMES),
            thinking=_thinking(ctx.chat, ctx.progress),
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


def route_after_agent(state: State) -> AfterAgent:
    if state["pending_tool_calls"]:
        return "tools"
    return "grade_evidence"


def route_after_tools(state: State, *, max_rounds: int) -> AfterTools:
    if state["tool_rounds"] < max_rounds:
        return "agent"
    return "grade_evidence"


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


def make_grade_evidence_node(ctx: NodeContext):
    async def grade_evidence_node(state: State) -> dict[str, object]:
        evidence: Sequence[ScoredChunk] = ctx.tool_ctx.evidence
        if evidence:
            return {"answer": None}

        question = state["question"]
        if ctx.progress is not None:
            await ctx.progress.stage("suggest")
        phrase = _topic_phrase(question.text)
        return {
            "answer": _insufficient(
                question.text,
                reason=InsufficientReason.NO_RELEVANT_CHUNKS,
                auditor_role=question.auditor_role,
                topic=question.topic,
                uncertainties=(f"No indexed chunks were relevant enough to cover {phrase}.",),
            ),
        }

    return grade_evidence_node


def route_after_grade(state: State) -> AfterGrade:
    if state["answer"] is not None:
        return "__end__"
    return "generate"


def make_generate_node(ctx: NodeContext):
    async def generate_node(state: State) -> dict[str, object]:
        if ctx.progress is not None:
            await ctx.progress.stage("generate")

        evidence = ctx.tool_ctx.evidence
        question = state["question"]
        gen_messages = build_generation_messages(
            question=state["standalone_question"],
            scored=evidence,
            auditor_role=question.auditor_role,
            topic=question.topic,
        )
        try:
            generation = await ctx.chat.generate_structured(
                gen_messages,
                AnswerGenerationResult,
                thinking=_thinking(ctx.chat, ctx.progress),
            )
            result = generation.value
            usage = state["usage"] + generation.usage
        except IncompleteStructuredOutputError:
            result = AnswerGenerationResult(
                can_answer=False,
                answer_text="",
                decline_reason="The model could not produce a grounded answer for this question.",
                markers_used=(),
            )
            usage = state["usage"]

        if not result.can_answer or not result.answer_text.strip():
            if ctx.progress is not None:
                await ctx.progress.stage("suggest")
            return {
                "generation": result,
                "usage": usage,
                "answer": _insufficient(
                    question.text,
                    reason=InsufficientReason.MODEL_JUDGED_INSUFFICIENT,
                    auditor_role=question.auditor_role,
                    topic=question.topic,
                    uncertainties=uncertainties_from_generation(result),
                    suggested_client_questions=suggestions_from_generation(
                        result,
                        question_text=question.text,
                        auditor_role=question.auditor_role,
                        topic=question.topic,
                    ),
                ),
            }

        return {
            "generation": result,
            "usage": usage,
            "answer": None,
        }

    return generate_node


def route_after_generate(state: State) -> AfterGenerate:
    if state["answer"] is not None:
        return "__end__"
    return "finalize"


def make_finalize_node(ctx: NodeContext):
    async def finalize_node(state: State) -> dict[str, object]:
        if ctx.progress is not None:
            await ctx.progress.stage("finalize")

        generation = state["generation"]
        question = state["question"]
        if generation is None:
            if ctx.progress is not None:
                await ctx.progress.stage("suggest")
            return {
                "answer": _insufficient(
                    question.text,
                    reason=InsufficientReason.MODEL_JUDGED_INSUFFICIENT,
                    auditor_role=question.auditor_role,
                    topic=question.topic,
                ),
            }

        filtered = filter_and_build_citations(generation.answer_text, ctx.tool_ctx.evidence)
        if filtered is None:
            if ctx.progress is not None:
                await ctx.progress.stage("suggest")
            return {
                "answer": _insufficient(
                    question.text,
                    reason=InsufficientReason.MODEL_JUDGED_INSUFFICIENT,
                    auditor_role=question.auditor_role,
                    topic=question.topic,
                ),
            }

        text, citations = filtered
        return {"answer": Answered(text=text, citations=citations)}

    return finalize_node
