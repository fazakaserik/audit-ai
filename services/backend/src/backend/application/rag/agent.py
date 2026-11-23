"""Tool-calling ask agent: gather evidence, then structured grounded answer."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from backend.application.ports import (
    ChatMessage,
    ChatModel,
    DocumentRepository,
    DocumentStorage,
    Embedder,
    EngagementRepository,
    IncompleteStructuredOutputError,
    ScoredChunk,
    VectorIndex,
)
from backend.application.rag.citations import filter_and_build_citations
from backend.application.rag.nodes import default_client_suggestions
from backend.application.rag.progress import AskProgress
from backend.application.rag.prompts import (
    AnswerGenerationResult,
    build_agent_messages,
    build_generation_messages,
)
from backend.application.rag.tools import dispatch_tool, tool_specs
from backend.application.rag.tools.base import ToolContext
from backend.config import Settings
from backend.domain.answer import (
    Answer,
    Answered,
    Citation,
    InsufficientEvidence,
    InsufficientReason,
    Question,
)
from backend.domain.document import FolderPath
from backend.domain.engagement import EngagementId
from backend.domain.session import LlmUsage, Turn


@dataclass(frozen=True, slots=True)
class AskAgentDeps:
    chat: ChatModel
    embedder: Embedder
    vector_index: VectorIndex
    engagements: EngagementRepository
    documents: DocumentRepository
    storage: DocumentStorage
    settings: Settings
    progress: AskProgress | None = None


@dataclass(frozen=True, slots=True)
class AskAgentResult:
    answer: Answer
    standalone_question: str
    usage: LlmUsage


def _thinking(deps: AskAgentDeps):
    if deps.progress is None or not deps.chat.supports_thinking:
        return None
    return deps.progress.thinking_callbacks()


def _merge_usage(current: LlmUsage, addition: LlmUsage) -> LlmUsage:
    return current + addition


async def run_ask_agent(
    *,
    engagement_id: EngagementId,
    question: Question,
    folder_scope: FolderPath | None,
    prior_turns: Sequence[Turn],
    deps: AskAgentDeps,
) -> AskAgentResult:
    limit = deps.settings.session_context_turns
    recent = tuple(prior_turns[-limit:]) if limit > 0 else ()
    standalone_question = question.text
    usage = LlmUsage()

    if deps.progress is not None:
        await deps.progress.stage("agent")

    tool_ctx = ToolContext(
        engagement_id=engagement_id,
        folder_scope=folder_scope if folder_scope is not None else question.folder_scope,
        embedder=deps.embedder,
        vector_index=deps.vector_index,
        engagements=deps.engagements,
        documents=deps.documents,
        storage=deps.storage,
        settings=deps.settings,
        progress=deps.progress,
    )
    messages: list[ChatMessage] = list(
        build_agent_messages(
            question=question.text,
            prior_turns=recent,
            auditor_role=question.auditor_role,
            topic=question.topic,
            folder_scope=str(tool_ctx.folder_scope) if tool_ctx.folder_scope else None,
        )
    )
    specs = tool_specs()
    max_rounds = deps.settings.agent_max_tool_rounds

    for _ in range(max_rounds):
        turn = await deps.chat.complete_tool_turn(
            messages,
            specs,
            thinking=_thinking(deps),
        )
        usage = _merge_usage(usage, turn.usage)
        if not turn.tool_calls:
            break

        if deps.progress is not None:
            await deps.progress.stage("tool")

        messages.append(
            ChatMessage(
                role="assistant",
                content=turn.content,
                tool_calls=turn.tool_calls,
            )
        )
        for call in turn.tool_calls:
            if deps.progress is not None:
                await deps.progress.tool_call(name=call.name, arguments=call.arguments)
            result = await dispatch_tool(tool_ctx, call)
            if deps.progress is not None:
                await deps.progress.tool_result(name=call.name, summary=result.summary)
            messages.append(
                ChatMessage(
                    role="tool",
                    content=result.content,
                    tool_call_id=call.id,
                    name=call.name,
                )
            )
    else:
        # Max rounds exhausted while still requesting tools — continue with evidence so far.
        pass

    evidence: list[ScoredChunk] = tool_ctx.evidence
    if not evidence:
        answer = InsufficientEvidence(
            reason=InsufficientReason.NO_RELEVANT_CHUNKS,
            partial_citations=(),
            suggested_client_questions=default_client_suggestions(
                question.text,
                reason=InsufficientReason.NO_RELEVANT_CHUNKS,
                auditor_role=question.auditor_role,
                topic=question.topic,
            ),
        )
        if deps.progress is not None:
            await deps.progress.stage("suggest")
        return AskAgentResult(
            answer=answer,
            standalone_question=standalone_question,
            usage=usage,
        )

    if deps.progress is not None:
        await deps.progress.stage("generate")

    gen_messages = build_generation_messages(
        question=standalone_question,
        scored=evidence,
        auditor_role=question.auditor_role,
        topic=question.topic,
    )
    try:
        generation = await deps.chat.generate_structured(
            gen_messages,
            AnswerGenerationResult,
            thinking=_thinking(deps),
        )
        result = generation.value
        usage = _merge_usage(usage, generation.usage)
    except IncompleteStructuredOutputError:
        result = AnswerGenerationResult(
            can_answer=False,
            answer_text="",
            decline_reason="The model could not produce a grounded answer for this question.",
            markers_used=(),
        )

    if not result.can_answer or not result.answer_text.strip():
        if deps.progress is not None:
            await deps.progress.stage("suggest")
        return AskAgentResult(
            answer=InsufficientEvidence(
                reason=InsufficientReason.MODEL_JUDGED_INSUFFICIENT,
                partial_citations=(),
                suggested_client_questions=default_client_suggestions(
                    question.text,
                    reason=InsufficientReason.MODEL_JUDGED_INSUFFICIENT,
                    auditor_role=question.auditor_role,
                    topic=question.topic,
                ),
            ),
            standalone_question=standalone_question,
            usage=usage,
        )

    if deps.progress is not None:
        await deps.progress.stage("finalize")

    filtered = filter_and_build_citations(result.answer_text, evidence)
    if filtered is None:
        if deps.progress is not None:
            await deps.progress.stage("suggest")
        partial: tuple[Citation, ...] = ()
        return AskAgentResult(
            answer=InsufficientEvidence(
                reason=InsufficientReason.MODEL_JUDGED_INSUFFICIENT,
                partial_citations=partial,
                suggested_client_questions=default_client_suggestions(
                    question.text,
                    reason=InsufficientReason.MODEL_JUDGED_INSUFFICIENT,
                    auditor_role=question.auditor_role,
                    topic=question.topic,
                ),
            ),
            standalone_question=standalone_question,
            usage=usage,
        )

    text, citations = filtered
    return AskAgentResult(
        answer=Answered(text=text, citations=citations),
        standalone_question=standalone_question,
        usage=usage,
    )
