"""Final evidence check: validate that draft statements are grounded."""

from __future__ import annotations

import re
from collections.abc import Sequence

from backend.application.agents.research_agent.citations import filter_and_build_citations
from backend.application.agents.research_agent.state import State
from backend.application.dto import ChatMessage, ScoredChunk
from backend.domain.answer import Answered, InsufficientReason

from ._helpers import insufficient_answer, partial_citations_from_evidence
from .context import NodeContext
from .suggestions import default_client_suggestions, topic_phrase

_MARKER_RE = re.compile(r"\[\d+\]")

_CRITIQUE = (
    "Your previous draft failed the evidence check: statements that need "
    "engagement data must be supported by tool evidence and cited with [n] "
    "markers matching evidence indices. Gather more evidence with tools or "
    "revise the answer. Do not invent document facts."
)


def _has_citation_markers(text: str) -> bool:
    return _MARKER_RE.search(text) is not None


def make_check_node(ctx: NodeContext):
    max_restarts = ctx.settings.agent_max_check_restarts

    async def check_node(state: State) -> dict[str, object]:
        if ctx.progress is not None:
            await ctx.progress.stage("check")

        question = state["question"]
        draft = (state.get("draft_answer") or "").strip()
        evidence = ctx.tool_ctx.evidence
        tool_facts = ctx.tool_ctx.tool_facts
        topic_text = state["standalone_question"] or question.text

        accepted = _try_accept_draft(draft, evidence=evidence, tool_facts=tool_facts)
        if accepted is not None:
            return {"answer": accepted, "draft_answer": draft or None}

        restarts = state["check_restarts"]
        if restarts < max_restarts:
            messages = list(state["messages"])
            messages.append(ChatMessage(role="user", content=_CRITIQUE))
            return {
                "messages": messages,
                "draft_answer": None,
                "check_restarts": restarts + 1,
                "answer": None,
            }

        if ctx.progress is not None:
            await ctx.progress.stage("suggest")

        reason = (
            InsufficientReason.NO_RELEVANT_CHUNKS
            if not evidence and not tool_facts
            else InsufficientReason.MODEL_JUDGED_INSUFFICIENT
        )
        uncertainties: tuple[str, ...]
        if not draft:
            uncertainties = ("The assistant produced no answer text to verify.",)
        elif not evidence and not tool_facts:
            phrase = topic_phrase(topic_text)
            uncertainties = (
                f"No indexed chunks or tool facts supported statements about {phrase}.",
            )
        else:
            uncertainties = (
                "The draft's statements were not adequately cited against the evidence bag.",
            )

        return {
            "draft_answer": draft or None,
            "answer": insufficient_answer(
                topic_text,
                reason=reason,
                auditor_role=question.auditor_role,
                topic=question.topic,
                partial_citations=partial_citations_from_evidence(evidence),
                uncertainties=uncertainties,
                suggested_client_questions=default_client_suggestions(
                    topic_text,
                    reason=reason,
                    auditor_role=question.auditor_role,
                    topic=question.topic,
                ),
            ),
        }

    return check_node


def _try_accept_draft(
    draft: str,
    *,
    evidence: Sequence[ScoredChunk],
    tool_facts: Sequence[str],
) -> Answered | None:
    if not draft:
        return None

    if evidence:
        filtered = filter_and_build_citations(draft, evidence, markers_used=())
        if filtered is None:
            return None
        text, citations = filtered
        return Answered(text=text, citations=citations)

    if _has_citation_markers(draft):
        # Claimed document citations with an empty evidence bag.
        return None

    # Conversational reply or tool-fact-only answer (no document chunks).
    _ = tool_facts
    return Answered(text=draft, citations=())
