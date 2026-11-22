"""Ask pipeline: retrieve → grade → generate → finalize (or insufficient suggestions).

Node functions are composed here as an explicit state machine. A LangGraph
``StateGraph`` wrapper can replace this runner when the environment supports
``ormsgpack``; the node contracts stay identical.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import assert_never

from backend.rag.nodes import (
    AskGraphDeps,
    condense_question,
    finalize,
    generate_answer,
    grade_evidence,
    retrieve,
    route_after_finalize,
    route_after_generate,
    route_after_grade,
    route_after_retrieve,
    suggest_client_questions,
)
from backend.rag.state import AskState
from domain.answer import Answer, Question
from domain.document import FolderPath
from domain.engagement import EngagementId
from domain.session import Turn


@dataclass(frozen=True, slots=True)
class AskGraphResult:
    answer: Answer
    standalone_question: str


async def run_ask_graph(
    *,
    engagement_id: EngagementId,
    question: Question,
    folder_scope: FolderPath | None,
    prior_turns: Sequence[Turn] = (),
    deps: AskGraphDeps,
) -> AskGraphResult:
    state: AskState = {
        "engagement_id": engagement_id,
        "question": question,
        "folder_scope": folder_scope,
        "prior_turns": tuple(prior_turns),
    }

    state = {**state, **(await condense_question(state, deps))}
    standalone_question = state.get("standalone_question", question.text)

    state = {**state, **(await retrieve(state, deps))}
    after_retrieve = route_after_retrieve(state)
    if after_retrieve == "suggest_client_questions":
        state = {**state, **(await suggest_client_questions(state, deps))}
        return _require_result(state, standalone_question)
    if after_retrieve != "grade_evidence":
        assert_never(after_retrieve)

    state = {**state, **(await grade_evidence(state, deps))}
    after_grade = route_after_grade(state)
    if after_grade == "suggest_client_questions":
        state = {**state, **(await suggest_client_questions(state, deps))}
        return _require_result(state, standalone_question)
    if after_grade != "generate_answer":
        assert_never(after_grade)

    state = {**state, **(await generate_answer(state, deps))}
    after_generate = route_after_generate(state)
    if after_generate == "suggest_client_questions":
        state = {**state, **(await suggest_client_questions(state, deps))}
        return _require_result(state, standalone_question)
    if after_generate != "finalize":
        assert_never(after_generate)

    state = {**state, **(await finalize(state, deps))}
    after_finalize = route_after_finalize(state)
    if after_finalize == "suggest_client_questions":
        state = {**state, **(await suggest_client_questions(state, deps))}
        return _require_result(state, standalone_question)
    if after_finalize != "__end__":
        assert_never(after_finalize)
    return _require_result(state, standalone_question)


def _require_result(state: AskState, standalone_question: str) -> AskGraphResult:
    answer = state.get("answer")
    if answer is None:
        msg = "ask graph finished without an answer"
        raise RuntimeError(msg)
    return AskGraphResult(answer=answer, standalone_question=standalone_question)
