"""Research-agent prompt builders and structured output schemas."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from backend.application.dto import (
    ChatMessage,
    ScoredChunk,
)
from backend.domain.answer import Answered, InsufficientEvidence
from backend.domain.session import Turn

_CFG = ConfigDict(frozen=True, strict=True, extra="forbid")

# Field name is can_answer (not "sufficient") — thinking models misread "sufficient"
# as English prose and loop on whether the instruction is a typo.
_SYSTEM = """\
You are an audit assistant. Base every factual claim ONLY on the tool facts and/or \
numbered source chunks below. Do not invent policy rules, amounts, dates, names, \
or other data that those sources do not state.

The Question may be a short follow-up; use Recent conversation together with the \
tool facts / chunks to resolve pronouns and ellipsis, then answer the intended \
question.

Ordinary language understanding is allowed: you may map everyday wording in the \
question onto terms that appear in the chunks (for example treating a common \
instance as covered by a broader term the policy uses). When you do, answer with \
the document's own wording and cite it. State the policy condition clearly.

Prefer a grounded answer over declining when the sources support the asked point. \
Decline only when they truly do not (missing clause, missing definition, \
contradictory evidence, or an unclear question that Recent conversation cannot \
resolve).

When source chunks support the answer: every document-grounded claim needs an \
inline citation like [1]. After the cited claims you may add at most one short \
sentence naming any residual uncertainty — do not invent facts to fill the gap.

When answering from tool facts alone (no source chunks): write a clear short \
answer with no [n] citation markers.

When you decline: list concrete uncertainties (what is missing or ambiguous) and \
1-3 full client questions (complete interrogatives starting with What/Which/Who/How/ \
Where/When/Does/Is/Are/Can). Each question must ask for missing information the \
engagement lacks - never restate the auditor's question as a yes/no, and never use \
fragment prompts like "description of X".

Work briefly, then output one JSON object and stop. Do not revisit the decision.

JSON shape when you can answer:
{"can_answer": true, "answer_text": "<markdown, with [n] only if chunks are cited>", \
"decline_reason": "", "markers_used": [1], "uncertainties": [], "client_questions": []}

JSON shape when you decline:
{"can_answer": false, "answer_text": "", \
"decline_reason": "<one short sentence>", "markers_used": [], \
"uncertainties": ["<what is missing or ambiguous>"], \
"client_questions": ["What is the definition of beer under this policy?", \
"Which document states whether beer is reimbursable?"]}
"""


class AnswerGenerationResult(BaseModel):
    """Structured model output for grounded answer generation."""

    model_config = _CFG

    can_answer: bool
    answer_text: Annotated[str, Field(max_length=8000)] = ""
    decline_reason: Annotated[str, Field(max_length=500)] = ""
    markers_used: tuple[int, ...] = ()
    uncertainties: Annotated[tuple[str, ...], Field(max_length=5)] = ()
    client_questions: Annotated[tuple[str, ...], Field(max_length=3)] = ()


_AGENT_SYSTEM = """\
You are an audit assistant with tools for searching and browsing engagement documents.

Think briefly about what evidence you need, then emit a real tool call.
Describing a tool in thought is not enough — you must call it.
Prefer search_relevant_chunks with focused queries (ids, clause names, amounts, dates).
When the question uses everyday wording, also search the broader policy terms the \
documents are likely to use.
Use list_documents to explore folders and read_document for markdown/text files.
Use get_current_time when the question depends on now, today, or relative dates.
You may call tools multiple times. Do not invent document facts.

When you have enough evidence — or after tools return nothing useful — stop calling tools.
Do not write the final JSON answer in the tool loop; a later step will ask for that.
"""


def _format_chunks(scored: Sequence[ScoredChunk]) -> str:
    blocks: list[str] = []
    for index, row in enumerate(scored, start=1):
        page = f", page {row.chunk.page}" if row.chunk.page is not None else ""
        heading = " > ".join(row.chunk.heading_path) if row.chunk.heading_path else ""
        meta = f"{row.document_path}{page}"
        if heading:
            meta = f"{meta} ({heading})"
        blocks.append(f"[{index}] ({meta})\n{row.chunk.text}")
    return "\n\n".join(blocks)


def build_agent_messages(
    *,
    question: str,
    prior_turns: Sequence[Turn],
    auditor_role: str | None,
    topic: str | None,
    folder_scope: str | None,
) -> tuple[ChatMessage, ...]:
    lines: list[str] = []
    if prior_turns:
        lines.append("Recent conversation (for reference resolution only; not evidence):")
        for turn in prior_turns:
            lines.append(f"- User asked: {turn.standalone_question}")
        lines.append("")
    lines.append(f"Question: {question}")
    if auditor_role:
        lines.append(f"Auditor role: {auditor_role}")
    if topic:
        lines.append(f"Topic: {topic}")
    if folder_scope:
        lines.append(f"Folder scope: {folder_scope}")
    lines.append("")
    lines.append("Gather evidence with tools, then stop when ready to answer or decline.")
    return (
        ChatMessage(role="system", content=_AGENT_SYSTEM),
        ChatMessage(role="user", content="\n".join(lines)),
    )


def _prior_answer_summary(turn: Turn) -> str:
    answer = turn.answer
    if isinstance(answer, Answered):
        text = answer.text.strip().replace("\n", " ")
        return text if len(text) <= 240 else f"{text[:237]}..."
    if isinstance(answer, InsufficientEvidence):
        return f"(insufficient: {answer.reason.value})"
    return "(no answer)"


def build_generation_messages(
    *,
    question: str,
    scored: Sequence[ScoredChunk],
    auditor_role: str | None,
    topic: str | None,
    tool_facts: Sequence[str] = (),
    prior_turns: Sequence[Turn] = (),
) -> tuple[ChatMessage, ...]:
    context_lines: list[str] = []
    if prior_turns:
        context_lines.append("Recent conversation (resolve follow-ups; not evidence):")
        for turn in prior_turns:
            context_lines.append(f"- User asked: {turn.standalone_question}")
            context_lines.append(f"  Assistant: {_prior_answer_summary(turn)}")
        context_lines.append("")
    context_lines.append(f"Question: {question}")
    if auditor_role:
        context_lines.append(f"Auditor role: {auditor_role}")
    if topic:
        context_lines.append(f"Topic: {topic}")
    context_lines.append("")
    if tool_facts:
        context_lines.append("Tool facts:")
        for index, fact in enumerate(tool_facts, start=1):
            context_lines.append(f"(tool {index})\n{fact}")
        context_lines.append("")
    if scored:
        context_lines.append("Source chunks:")
        context_lines.append(_format_chunks(scored))
    elif not tool_facts:
        context_lines.append("Source chunks:")
        context_lines.append("(none)")
    user_content = "\n".join(context_lines)
    return (
        ChatMessage(role="system", content=_SYSTEM),
        ChatMessage(role="user", content=user_content),
    )
