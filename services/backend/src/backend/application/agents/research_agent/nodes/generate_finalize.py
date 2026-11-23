"""Evidence grading, answer generation, and citation finalization nodes."""

from __future__ import annotations

from collections.abc import Sequence

from backend.application.agents.research_agent.citations import filter_and_build_citations
from backend.application.agents.research_agent.prompts import (
    AnswerGenerationResult,
    build_generation_messages,
)
from backend.application.agents.research_agent.state import State
from backend.application.dto import IncompleteStructuredOutputError, ScoredChunk
from backend.domain.answer import Answered, InsufficientReason

from ._helpers import insufficient_answer, thinking_callbacks, uncertainties_from_generation
from .context import NodeContext
from .suggestions import suggestions_from_generation, topic_phrase


def make_grade_evidence_node(ctx: NodeContext):
    async def grade_evidence_node(state: State) -> dict[str, object]:
        evidence: Sequence[ScoredChunk] = ctx.tool_ctx.evidence
        if evidence:
            return {"answer": None}

        question = state["question"]
        if ctx.progress is not None:
            await ctx.progress.stage("suggest")
        phrase = topic_phrase(question.text)
        return {
            "answer": insufficient_answer(
                question.text,
                reason=InsufficientReason.NO_RELEVANT_CHUNKS,
                auditor_role=question.auditor_role,
                topic=question.topic,
                uncertainties=(f"No indexed chunks were relevant enough to cover {phrase}.",),
            ),
        }

    return grade_evidence_node


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
                thinking=thinking_callbacks(ctx.chat, ctx.progress),
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
                "answer": insufficient_answer(
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
                "answer": insufficient_answer(
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
                "answer": insufficient_answer(
                    question.text,
                    reason=InsufficientReason.MODEL_JUDGED_INSUFFICIENT,
                    auditor_role=question.auditor_role,
                    topic=question.topic,
                ),
            }

        text, citations = filtered
        return {"answer": Answered(text=text, citations=citations)}

    return finalize_node
