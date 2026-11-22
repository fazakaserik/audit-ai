"""LangGraph nodes for retrieve → grade → generate → finalize."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from backend.application.ports import ChatModel, Embedder, RetrievalScope, VectorIndex
from backend.config import Settings
from backend.rag.citations import filter_and_build_citations
from backend.rag.progress import AskProgress, SourceHit
from backend.rag.prompts import (
    AnswerGenerationResult,
    CondenseQuestionResult,
    build_condense_messages,
    build_generation_messages,
)
from backend.rag.state import AskState
from domain.answer import (
    Answered,
    Citation,
    InsufficientEvidence,
    InsufficientReason,
    SuggestedClientQuestion,
)
from domain.session import LlmUsage


def _merge_usage(state: AskState, usage: LlmUsage) -> LlmUsage:
    current = state.get("usage")
    if current is None:
        return usage
    return current + usage


@dataclass(frozen=True, slots=True)
class AskGraphDeps:
    chat: ChatModel
    embedder: Embedder
    vector_index: VectorIndex
    settings: Settings
    progress: AskProgress | None = None


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def default_client_suggestions(
    question_text: str,
    *,
    reason: InsufficientReason,
    auditor_role: str | None = None,
    topic: str | None = None,
) -> tuple[SuggestedClientQuestion, ...]:
    prompt = _truncate(question_text.strip(), 200)
    role_bit = f" for the {auditor_role} reviewer" if auditor_role else ""
    topic_bit = f" regarding {topic}" if topic else ""
    if reason == InsufficientReason.NO_RELEVANT_PASSAGES:
        return (
            SuggestedClientQuestion(
                question=(
                    f"Can you provide documents{role_bit} that answer: {prompt}{topic_bit}?"
                ),
                rationale="No indexed passages met the relevance threshold for this question.",
            ),
            SuggestedClientQuestion(
                question=(
                    "Are there additional files in a different folder that cover "
                    f"this{topic_bit or ' topic'}?"
                ),
                rationale="The current folder scope may not include the relevant records.",
            ),
        )
    return (
        SuggestedClientQuestion(
            question=(
                f"Can you provide clearer or additional documentation{role_bit} "
                f"about: {prompt}{topic_bit}?"
            ),
            rationale="Retrieved passages were not sufficient to ground a cited answer.",
        ),
    )


def _query_text(state: AskState) -> str:
    standalone = state.get("standalone_question")
    if standalone is not None and standalone.strip():
        return standalone
    return state["question"].text


def _thinking(deps: AskGraphDeps):
    if deps.progress is None or not deps.chat.supports_thinking:
        return None
    return deps.progress.thinking_callbacks()


async def condense_question(state: AskState, deps: AskGraphDeps) -> AskState:
    question = state["question"]
    prior = state.get("prior_turns", ())
    if not prior:
        return {"standalone_question": question.text}

    if deps.progress is not None:
        await deps.progress.stage("condense")

    limit = deps.settings.session_context_turns
    recent = prior[-limit:] if limit > 0 else ()
    messages = build_condense_messages(prior_turns=recent, new_question=question.text)
    result = await deps.chat.generate_structured(
        messages,
        CondenseQuestionResult,
        thinking=_thinking(deps),
    )
    return {
        "standalone_question": result.value.standalone_question,
        "usage": _merge_usage(state, result.usage),
    }


async def retrieve(state: AskState, deps: AskGraphDeps) -> AskState:
    if deps.progress is not None:
        await deps.progress.stage("retrieve")
    question = state["question"]
    query_text = _query_text(state)
    folder = state.get("folder_scope", question.folder_scope)
    embedded = await deps.embedder.embed((query_text,))
    scope = RetrievalScope(
        engagement_id=state["engagement_id"],
        folder_prefix=folder,
        top_k=deps.settings.retrieval_top_k,
    )
    scored = await deps.vector_index.search(
        query_text,
        embedded.vectors[0],
        scope,
        embedding_model=deps.embedder.model_name,
        min_score=deps.settings.relevance_threshold,
    )
    if deps.progress is not None and scored:
        await deps.progress.sources(
            [SourceHit(path=row.document_path, score=row.score) for row in scored]
        )
    update: AskState = {
        "scored_passages": scored,
        "usage": _merge_usage(state, embedded.usage),
    }
    if not scored:
        update["insufficient_reason"] = InsufficientReason.NO_RELEVANT_PASSAGES
    return update


async def grade_evidence(state: AskState, deps: AskGraphDeps) -> AskState:
    if deps.progress is not None:
        await deps.progress.stage("grade")
    scored = state.get("scored_passages", [])
    if not scored:
        return {"insufficient_reason": InsufficientReason.NO_RELEVANT_PASSAGES}
    return {}


async def generate_answer(state: AskState, deps: AskGraphDeps) -> AskState:
    if deps.progress is not None:
        await deps.progress.stage("generate")
    question = state["question"]
    scored = state["scored_passages"]
    messages = build_generation_messages(
        question=_query_text(state),
        scored=scored,
        auditor_role=question.auditor_role,
        topic=question.topic,
    )
    generation = await deps.chat.generate_structured(
        messages,
        AnswerGenerationResult,
        thinking=_thinking(deps),
    )
    update: AskState = {
        "generation": generation.value,
        "usage": _merge_usage(state, generation.usage),
    }
    if not generation.value.sufficient or not generation.value.answer_text.strip():
        update["insufficient_reason"] = InsufficientReason.MODEL_JUDGED_INSUFFICIENT
    return update


async def finalize(state: AskState, deps: AskGraphDeps) -> AskState:
    if deps.progress is not None:
        await deps.progress.stage("finalize")
    generation = state.get("generation")
    if generation is None:
        return {"insufficient_reason": InsufficientReason.MODEL_JUDGED_INSUFFICIENT}
    scored = state.get("scored_passages", [])
    filtered = filter_and_build_citations(generation.answer_text, scored)
    if filtered is None:
        partial: tuple[Citation, ...] = ()
        return {
            "insufficient_reason": InsufficientReason.MODEL_JUDGED_INSUFFICIENT,
            "partial_citations": partial,
        }
    text, citations = filtered
    return {"answer": Answered(text=text, citations=citations)}


async def suggest_client_questions(state: AskState, deps: AskGraphDeps) -> AskState:
    if deps.progress is not None:
        await deps.progress.stage("suggest")
    reason = state.get("insufficient_reason", InsufficientReason.MODEL_JUDGED_INSUFFICIENT)
    partial = state.get("partial_citations", ())
    question = state["question"]
    suggestions = default_client_suggestions(
        question.text,
        reason=reason,
        auditor_role=question.auditor_role,
        topic=question.topic,
    )
    return {
        "answer": InsufficientEvidence(
            reason=reason,
            partial_citations=partial,
            suggested_client_questions=suggestions,
        ),
    }


def route_after_retrieve(state: AskState) -> Literal["grade_evidence", "suggest_client_questions"]:
    if state.get("insufficient_reason") == InsufficientReason.NO_RELEVANT_PASSAGES:
        return "suggest_client_questions"
    return "grade_evidence"


def route_after_grade(state: AskState) -> Literal["generate_answer", "suggest_client_questions"]:
    if state.get("insufficient_reason") == InsufficientReason.NO_RELEVANT_PASSAGES:
        return "suggest_client_questions"
    if not state.get("scored_passages"):
        return "suggest_client_questions"
    return "generate_answer"


def route_after_generate(state: AskState) -> Literal["finalize", "suggest_client_questions"]:
    if state.get("insufficient_reason") == InsufficientReason.MODEL_JUDGED_INSUFFICIENT:
        return "suggest_client_questions"
    return "finalize"


def route_after_finalize(state: AskState) -> Literal["suggest_client_questions", "__end__"]:
    if state.get("answer") is not None:
        return "__end__"
    return "suggest_client_questions"
