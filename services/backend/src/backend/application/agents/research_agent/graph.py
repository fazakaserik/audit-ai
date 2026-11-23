"""Research pipeline: LangGraph StateGraph over the tool-calling agent."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from backend.application.agents._langgraph import END, START, StateGraph
from backend.application.agents.progress import AskProgress
from backend.application.agents.research_agent.nodes import (
    AfterTools,
    NodeContext,
    make_agent_node,
    make_finalize_node,
    make_generate_node,
    make_grade_evidence_node,
    make_tools_node,
    route_after_agent,
    route_after_generate,
    route_after_grade,
    route_after_tools,
)
from backend.application.agents.research_agent.prompts import build_agent_messages
from backend.application.agents.research_agent.state import State
from backend.application.llm.chat_model import ChatModel
from backend.application.llm.embedder import Embedder
from backend.application.repositories.document import DocumentRepository
from backend.application.repositories.engagement import EngagementRepository
from backend.application.storage.document_storage import DocumentStorage
from backend.application.storage.vector_index import VectorIndex
from backend.application.tools.base import ToolContext
from backend.config import Settings
from backend.domain.answer import Answer, Question
from backend.domain.document import FolderPath
from backend.domain.engagement import EngagementId
from backend.domain.session import LlmUsage, Turn


@dataclass(frozen=True, slots=True)
class GraphDeps:
    chat: ChatModel
    embedder: Embedder
    vector_index: VectorIndex
    engagements: EngagementRepository
    documents: DocumentRepository
    storage: DocumentStorage
    settings: Settings
    progress: AskProgress | None = None


@dataclass(frozen=True, slots=True)
class GraphResult:
    answer: Answer
    standalone_question: str
    usage: LlmUsage


def _compile_graph(ctx: NodeContext):
    max_rounds = ctx.settings.agent_max_tool_rounds

    def tools_router(state: State) -> AfterTools:
        return route_after_tools(state, max_rounds=max_rounds)

    builder = StateGraph(State)
    builder.add_node("agent", make_agent_node(ctx))
    builder.add_node("tools", make_tools_node(ctx))
    builder.add_node("grade_evidence", make_grade_evidence_node(ctx))
    builder.add_node("generate", make_generate_node(ctx))
    builder.add_node("finalize", make_finalize_node(ctx))

    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "grade_evidence": "grade_evidence"},
    )
    builder.add_conditional_edges(
        "tools",
        tools_router,
        {"agent": "agent", "grade_evidence": "grade_evidence"},
    )
    builder.add_conditional_edges(
        "grade_evidence",
        route_after_grade,
        {"generate": "generate", "__end__": END},
    )
    builder.add_conditional_edges(
        "generate",
        route_after_generate,
        {"finalize": "finalize", "__end__": END},
    )
    builder.add_edge("finalize", END)
    return builder.compile()


async def run_graph(
    *,
    engagement_id: EngagementId,
    question: Question,
    folder_scope: FolderPath | None,
    prior_turns: Sequence[Turn] = (),
    deps: GraphDeps,
    progress: AskProgress | None = None,
) -> GraphResult:
    progress_sink = progress if progress is not None else deps.progress
    limit = deps.settings.session_context_turns
    recent = tuple(prior_turns[-limit:]) if limit > 0 else ()
    standalone_question = question.text

    if progress_sink is not None:
        await progress_sink.stage("agent")

    tool_ctx = ToolContext(
        engagement_id=engagement_id,
        folder_scope=folder_scope if folder_scope is not None else question.folder_scope,
        embedder=deps.embedder,
        vector_index=deps.vector_index,
        engagements=deps.engagements,
        documents=deps.documents,
        storage=deps.storage,
        settings=deps.settings,
        progress=progress_sink,
    )
    messages = list(
        build_agent_messages(
            question=question.text,
            prior_turns=recent,
            auditor_role=question.auditor_role,
            topic=question.topic,
            folder_scope=str(tool_ctx.folder_scope) if tool_ctx.folder_scope else None,
        )
    )
    ctx = NodeContext(
        chat=deps.chat,
        settings=deps.settings,
        tool_ctx=tool_ctx,
        progress=progress_sink,
    )
    graph = _compile_graph(ctx)
    initial: State = {
        "question": question,
        "standalone_question": standalone_question,
        "messages": messages,
        "tool_rounds": 0,
        "pending_tool_calls": (),
        "usage": LlmUsage(),
        "generation": None,
        "answer": None,
    }
    final = await graph.ainvoke(initial)
    answer = final.get("answer")
    if answer is None:
        msg = "ask graph finished without an answer"
        raise RuntimeError(msg)
    return GraphResult(
        answer=answer,
        standalone_question=final["standalone_question"],
        usage=final["usage"],
    )
