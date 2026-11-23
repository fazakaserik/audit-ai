"""API test: POST ask/stream emits stages, sources, thinking, then final."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import httpx

from backend.application.agents.research_agent.prompts import AnswerGenerationResult
from backend.application.api.dependencies import get_bound
from backend.application.api.main import create_app
from backend.domain.chunk import Chunk, ChunkId
from backend.domain.common import utc_now
from backend.domain.document import DocumentId
from backend.domain.engagement import Engagement, EngagementId
from support.fakes import (
    FakeChatModel,
    FakeEmbedder,
    InMemoryEngagementRepository,
    InMemoryVectorIndex,
    agent_search_tool_turns,
)
from support.test_container import build_fakes_bound, build_test_container


def _parse_sse(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for block in body.split("\n\n"):
        lines = [line for line in block.splitlines() if line.startswith("data:")]
        if not lines:
            continue
        payload = "\n".join(line.removeprefix("data:").strip() for line in lines)
        events.append(json.loads(payload))
    return events


async def test_post_ask_stream_progress_and_final() -> None:
    engagement_id = EngagementId("northwind-fy2025")
    engagements = InMemoryEngagementRepository()
    now = utc_now()
    await engagements.create(
        Engagement(
            id=engagement_id,
            name="Northwind FY2025",
            created_at=now,
            updated_at=now,
        )
    )

    chunk_text = "Meal reimbursement is capped at 75 USD per day."
    doc_id = DocumentId(uuid.uuid4())
    chunk = Chunk(
        id=ChunkId(uuid.uuid4()),
        document_id=doc_id,
        document_version=1,
        ordinal=0,
        page=1,
        heading_path=("Meals",),
        text=chunk_text,
        token_count=10,
        created_at=datetime.now(UTC),
    )

    embedder = FakeEmbedder()
    embedded = await embedder.embed((chunk_text, "meal limits"))
    vector_index = InMemoryVectorIndex()
    await vector_index.upsert_chunks(
        engagement_id=engagement_id,
        document_id=doc_id,
        document_path="policies/expense-policy.md",
        document_version=1,
        chunks=(chunk,),
        embeddings=(embedded.vectors[0],),
        embedding_model=embedder.model_name,
    )

    chat = FakeChatModel(
        tool_turns=agent_search_tool_turns(),
        response=AnswerGenerationResult(
            can_answer=True,
            answer_text="Meal limit is 75 USD per day [1].",
            markers_used=(1,),
        ),
        supports_thinking=True,
        thinking_text="Checking policy chunks…",
        thinking_seconds=1.26,
    )
    container = build_test_container(embedder=embedder, chat=chat)
    bound = build_fakes_bound(
        engagements=engagements,
        vector_index=vector_index,
        settings=container.settings,
        chat=chat,
        embedder=embedder,
        storage=container.document_storage,
    )
    app = create_app(settings=container.settings, container=container)

    async def override_bound():
        return bound

    app.dependency_overrides[get_bound] = override_bound

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/v1/engagements/{engagement_id}/ask/stream",
            json={"question": "What are the meal limits?"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        events = _parse_sse(response.text)
        types = [str(event.get("type")) for event in events]
        assert "stage" in types
        assert "sources" in types
        assert "thinking_delta" in types
        assert types.count("thinking_done") == 1
        assert types[-1] == "final"
        thinking_done = next(event for event in events if event.get("type") == "thinking_done")
        # Tool loop + generate each report thinking_seconds from the fake.
        assert thinking_done.get("duration_seconds") == round(1.26 * 3, 1)
        assert "tool_call" in types
        assert "tool_result" in types
        final = events[-1]["response"]
        assert isinstance(final, dict)
        assert final["status"] == "answered"
        assert final["usage"]["total_tokens"] >= 15
        assert final["session_total_tokens"] >= final["usage"]["total_tokens"]
        sources = next(event for event in events if event.get("type") == "sources")
        assert sources["sources"][0]["path"] == "policies/expense-policy.md"

        session_id = final["session_id"]
        detail = await client.get(
            f"/api/v1/engagements/{engagement_id}/sessions/{session_id}",
        )
        assert detail.status_code == 200
        turns = detail.json()["turns"]
        assert len(turns) == 1
        assert turns[0]["thinking_text"] == "Checking policy chunks…" * 3
        assert turns[0]["thinking_seconds"] == round(1.26 * 3, 1)
        assert turns[0]["answer"]["usage"]["total_tokens"] >= 15
