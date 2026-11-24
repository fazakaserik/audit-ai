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
numbered source chunks below. Do not invent facts those sources do not state.

The Question may be a short follow-up; use Conversation history together with the \
tool facts / chunks to resolve pronouns and ellipsis, then answer the intended \
question.

Ordinary language understanding is allowed: map everyday wording in the question \
onto terms that appear in the chunks. When you do, answer with the document's own \
wording and cite it.

Prefer a grounded answer over declining when the sources support the asked point. \
If they state what was asked, answer with can_answer true and cite them. Decline \
only when they do not (missing detail, contradictory evidence, or an unclear \
question that Conversation history cannot resolve).

When source chunks support the answer: every document-grounded claim needs an \
inline citation like [1] (and put those numbers in markers_used). After the cited \
claims you may add at most one short sentence naming any residual uncertainty — \
do not invent facts to fill the gap.

When answering from tool facts alone (no source chunks): write a clear short \
answer with no [n] citation markers.

When you decline: list concrete uncertainties (what is missing or ambiguous) and \
1-3 full client questions (complete interrogatives). Each must ask for missing \
information the engagement lacks — never restate the auditor's question as a \
yes/no, and never use fragment prompts.

Work briefly, then output one JSON object and stop. Do not revisit the decision.

JSON shape when you can answer:
{"can_answer": true, "answer_text": "<markdown, with [n] only if chunks are cited>", \
"decline_reason": "", "markers_used": [1], "uncertainties": [], "client_questions": []}

JSON shape when you decline:
{"can_answer": false, "answer_text": "", \
"decline_reason": "<one short sentence>", "markers_used": [], \
"uncertainties": ["<what is missing or ambiguous>"], \
"client_questions": ["<full interrogative asking for the missing detail>"]}
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
You are an audit assistant with tools that gather evidence from engagement documents \
(or the current time).

Think briefly about what evidence you need, then emit a real tool call.
Describing a tool in thought is not enough — you must call it.

Tools and what they add:
- search_relevant_chunks: adds matching document chunks to evidence (primary tool).
- read_document: loads a text file, or indexed chunks for a PDF/Office path, into \
evidence. Use when search finds a relevant path and you need more of that file.
- list_documents: browse folders/paths only (not evidence text).
- get_current_time: wall-clock time for "now"/today/relative dates (tool fact, not chunks).

Prefer focused search queries drawn from the question (identifiers, names, amounts, \
dates, document terms). When the question uses everyday wording, also search the \
broader terms documents are likely to use. You may call tools multiple times. \
Do not invent document facts.

When evidence already supports the asked point, stop calling tools — a later step \
will answer from that evidence. When a hit is incomplete for the asked detail, \
read or search further; when tools return nothing useful, stop.
Do not write the final JSON answer in the tool loop; a later step will ask for that.
"""


def _format_chunks(scored: Sequence[ScoredChunk], *, max_chars: int | None = None) -> str:
    blocks: list[str] = []
    used = 0
    for index, row in enumerate(scored, start=1):
        page = f", page {row.chunk.page}" if row.chunk.page is not None else ""
        heading = " > ".join(row.chunk.heading_path) if row.chunk.heading_path else ""
        meta = f"{row.document_path}{page}"
        if heading:
            meta = f"{meta} ({heading})"
        header = f"[{index}] ({meta})\n"
        text = row.chunk.text
        if max_chars is not None:
            remaining = max_chars - used - len(header)
            if remaining <= 0:
                break
            if len(text) > remaining:
                text = f"{text[: max(0, remaining - 3)]}..."
        block = f"{header}{text}"
        blocks.append(block)
        used += len(block) + 2  # account for joining "\n\n"
        if max_chars is not None and used >= max_chars:
            break
    return "\n\n".join(blocks)


def format_prior_answer(turn: Turn) -> str:
    """Full prior assistant reply for session history (not truncated)."""
    answer = turn.answer
    if isinstance(answer, Answered):
        return answer.text.strip() or "(empty answer)"
    if isinstance(answer, InsufficientEvidence):
        return f"(insufficient: {answer.reason.value})"
    return "(no answer)"


def _format_conversation_history(
    prior_turns: Sequence[Turn],
    *,
    older_summary: str | None = None,
) -> list[str]:
    lines = [
        "Conversation history (recent turns; resolve follow-ups; not evidence):",
    ]
    if older_summary:
        lines.append(f"Earlier session summary: {older_summary}")
        lines.append("")
    for turn in prior_turns:
        lines.append(f"- User: {turn.standalone_question}")
        lines.append(f"  Assistant: {format_prior_answer(turn)}")
    lines.append("")
    return lines


def build_agent_messages(
    *,
    question: str,
    prior_turns: Sequence[Turn],
    auditor_role: str | None,
    topic: str | None,
    folder_scope: str | None,
    older_summary: str | None = None,
) -> tuple[ChatMessage, ...]:
    lines: list[str] = []
    if prior_turns or older_summary:
        lines.extend(
            _format_conversation_history(prior_turns, older_summary=older_summary)
        )
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


def build_generation_messages(
    *,
    question: str,
    scored: Sequence[ScoredChunk],
    auditor_role: str | None,
    topic: str | None,
    tool_facts: Sequence[str] = (),
    prior_turns: Sequence[Turn] = (),
    older_summary: str | None = None,
    evidence_max_chars: int | None = None,
) -> tuple[ChatMessage, ...]:
    context_lines: list[str] = []
    if prior_turns or older_summary:
        context_lines.extend(
            _format_conversation_history(prior_turns, older_summary=older_summary)
        )
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
        context_lines.append(_format_chunks(scored, max_chars=evidence_max_chars))
    elif not tool_facts:
        context_lines.append("Source chunks:")
        context_lines.append("(none)")
    user_content = "\n".join(context_lines)
    return (
        ChatMessage(role="system", content=_SYSTEM),
        ChatMessage(role="user", content=user_content),
    )
