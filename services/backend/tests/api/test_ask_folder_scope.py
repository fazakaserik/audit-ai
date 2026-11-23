"""API test: folder_prefix scopes retrieval."""

from __future__ import annotations

from backend.domain.engagement import EngagementId
from support.ask_api import (
    answered_chat,
    build_ask_app,
    index_chunk,
    post_ask,
    seed_engagement,
)
from support.fakes import FakeEmbedder, InMemoryEngagementRepository, InMemoryVectorIndex


async def test_folder_prefix_scopes_retrieval() -> None:
    engagement_id: EngagementId = "northwind-fy2025"
    engagements = InMemoryEngagementRepository()
    await seed_engagement(engagements, engagement_id)

    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    await index_chunk(
        vector_index,
        embedder,
        engagement_id=engagement_id,
        path="contracts/contoso-msa.md",
        text="Payment is due within 30 days of invoice.",
    )
    await index_chunk(
        vector_index,
        embedder,
        engagement_id=engagement_id,
        path="policies/expense-policy.md",
        text="Domestic meal limit is USD 75 per day.",
    )

    app = build_ask_app(
        engagements=engagements,
        vector_index=vector_index,
        embedder=embedder,
        chat=answered_chat("Payment is due within 30 days [1]."),
    )
    response = await post_ask(
        app,
        engagement_id,
        {
            "question": "What are the payment terms?",
            "folder_prefix": "contracts",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["citations"][0]["document_path"].startswith("contracts/")
