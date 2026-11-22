"""RAG prompt builders and structured output schemas."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from backend.application.ports import ChatMessage, ScoredPassage
from domain.session import Turn

_CFG = ConfigDict(frozen=True, strict=True, extra="forbid")

_SYSTEM = """\
You are an audit assistant. Answer ONLY using the numbered source passages below.
Do not use general knowledge, assumptions, or information outside the passages.
Every factual claim MUST be followed by an inline citation marker [n] matching a passage number.
If the passages do not contain enough evidence to answer, set sufficient to false and leave answer_text empty.
"""


class AnswerGenerationResult(BaseModel):
    """Structured model output for grounded answer generation."""

    model_config = _CFG

    sufficient: bool
    answer_text: Annotated[str, Field(max_length=8000)] = ""
    markers_used: tuple[int, ...] = ()


class SuggestedQuestionsResult(BaseModel):
    """Optional structured client-question suggestions from the model."""

    model_config = _CFG

    questions: Annotated[
        tuple[str, ...],
        Field(min_length=1, max_length=3),
    ]


_CONDENSE_SYSTEM = """\
You rewrite follow-up audit questions into a single standalone question.
Use the conversation history for context only — do not copy prior answers into the question.
The standalone question must be fully self-contained and suitable for document search.
"""


class CondenseQuestionResult(BaseModel):
    """Structured output for session follow-up question condensation."""

    model_config = _CFG

    standalone_question: Annotated[str, Field(min_length=1, max_length=4000)]


def _format_passages(scored: Sequence[ScoredPassage]) -> str:
    blocks: list[str] = []
    for index, row in enumerate(scored, start=1):
        page = f", page {row.passage.page}" if row.passage.page is not None else ""
        heading = (
            " > ".join(row.passage.heading_path) if row.passage.heading_path else ""
        )
        meta = f"{row.document_path}{page}"
        if heading:
            meta = f"{meta} ({heading})"
        blocks.append(f"[{index}] ({meta})\n{row.passage.text}")
    return "\n\n".join(blocks)


def build_condense_messages(
    *,
    prior_turns: Sequence[Turn],
    new_question: str,
) -> tuple[ChatMessage, ...]:
    lines: list[str] = ["Conversation history:"]
    for turn in prior_turns:
        lines.append(f"User: {turn.standalone_question}")
        lines.append("Assistant: [prior answer omitted from evidence]")
    lines.append("")
    lines.append(f"New follow-up question: {new_question}")
    lines.append("")
    lines.append("Rewrite the follow-up as one standalone question for document search.")
    user_content = "\n".join(lines)
    return (
        ChatMessage(role="system", content=_CONDENSE_SYSTEM),
        ChatMessage(role="user", content=user_content),
    )


def build_generation_messages(
    *,
    question: str,
    scored: Sequence[ScoredPassage],
    auditor_role: str | None,
    topic: str | None,
) -> tuple[ChatMessage, ...]:
    context_lines: list[str] = [f"Question: {question}"]
    if auditor_role:
        context_lines.append(f"Auditor role: {auditor_role}")
    if topic:
        context_lines.append(f"Topic: {topic}")
    context_lines.append("")
    context_lines.append("Source passages:")
    context_lines.append(_format_passages(scored))
    user_content = "\n".join(context_lines)
    return (
        ChatMessage(role="system", content=_SYSTEM),
        ChatMessage(role="user", content=user_content),
    )