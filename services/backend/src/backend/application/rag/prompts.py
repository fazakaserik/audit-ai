"""RAG prompt builders and structured output schemas."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from backend.application.ports import ChatMessage, ScoredChunk
from backend.domain.session import Turn

_CFG = ConfigDict(frozen=True, strict=True, extra="forbid")

# Field name is can_answer (not "sufficient") — thinking models misread "sufficient"
# as English prose and loop on whether the instruction is a typo.
_SYSTEM = """\
You are an audit assistant. Use ONLY the numbered source chunks below.
Do not use general knowledge or information outside those chunks.
Every factual claim in an answer must include an inline citation like [1].

You may always decline. Decline when the question is unclear or the chunks \
do not support a grounded answer. Prefer declining over guessing.

Work briefly, then output one JSON object and stop. Do not revisit the decision.

JSON shape when you can answer:
{"can_answer": true, "answer_text": "<markdown with [n] citations>", "decline_reason": "", "markers_used": [1]}

JSON shape when you decline:
{"can_answer": false, "answer_text": "", "decline_reason": "<one short sentence>", "markers_used": []}
"""


class AnswerGenerationResult(BaseModel):
    """Structured model output for grounded answer generation."""

    model_config = _CFG

    can_answer: bool
    answer_text: Annotated[str, Field(max_length=8000)] = ""
    decline_reason: Annotated[str, Field(max_length=500)] = ""
    markers_used: tuple[int, ...] = ()


class SuggestedQuestionsResult(BaseModel):
    """Optional structured client-question suggestions from the model."""

    model_config = _CFG

    questions: Annotated[
        tuple[str, ...],
        Field(min_length=1, max_length=3),
    ]


_AGENT_SYSTEM = """\
You are an audit assistant with tools for searching and browsing engagement documents.

Think briefly about what evidence you need, then emit a real tool call.
Describing a tool in thought is not enough — you must call it.
Prefer search_relevant_chunks with focused queries (ids, clause names, amounts, dates).
Use list_documents to explore folders and read_document for markdown/text files.
You may call tools multiple times. Do not invent facts from general knowledge.

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


def build_generation_messages(
    *,
    question: str,
    scored: Sequence[ScoredChunk],
    auditor_role: str | None,
    topic: str | None,
) -> tuple[ChatMessage, ...]:
    context_lines: list[str] = [f"Question: {question}"]
    if auditor_role:
        context_lines.append(f"Auditor role: {auditor_role}")
    if topic:
        context_lines.append(f"Topic: {topic}")
    context_lines.append("")
    context_lines.append("Source chunks:")
    context_lines.append(_format_chunks(scored))
    user_content = "\n".join(context_lines)
    return (
        ChatMessage(role="system", content=_SYSTEM),
        ChatMessage(role="user", content=user_content),
    )
