"""Session history budget: only newest session_max_turns feed ask context."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from backend.application.agents.research_agent.history import (
    HistorySummaryResult,
    prepare_session_context,
)
from backend.application.services.ask import AskService
from backend.config import Settings
from backend.domain.answer import Answered, Question
from backend.domain.common import utc_now
from backend.domain.engagement import Engagement, EngagementId
from backend.domain.session import Session, SessionId, Turn, TurnId
from support.fakes import (
    FakeChatModel,
    FakeEmbedder,
    InMemoryDocumentRepository,
    InMemoryDocumentStorage,
    InMemoryEngagementRepository,
    InMemorySessionRepository,
    InMemoryVectorIndex,
)


def _turn(session_id: SessionId, ordinal: int) -> Turn:
    now = utc_now()
    return Turn(
        id=TurnId(uuid.uuid4()),
        session_id=session_id,
        ordinal=ordinal,
        question=Question(text=f"q{ordinal}"),
        standalone_question=f"q{ordinal}",
        answer=Answered(text=f"a{ordinal}", citations=()),
        created_at=now,
    )


async def test_prepare_session_context_uses_only_provided_window() -> None:
    session_id = SessionId(uuid.uuid4())
    turns = [_turn(session_id, i) for i in range(10)]
    chat = FakeChatModel(response=HistorySummaryResult(summary="Earlier turns summarized."))
    context, _usage = await prepare_session_context(
        turns,
        max_recent=3,
        chat=chat,
    )
    assert len(context.recent_turns) == 3
    assert context.recent_turns[0].ordinal == 7
    assert context.older_summary == "Earlier turns summarized."


async def test_ask_service_slices_to_session_max_turns() -> None:
    settings = Settings(session_context_turns=2, session_max_turns=3)
    engagements = InMemoryEngagementRepository()
    sessions = InMemorySessionRepository()
    now = utc_now()
    engagement_id = EngagementId("eng-history")
    await engagements.create(
        Engagement(id=engagement_id, name="Hist", created_at=now, updated_at=now)
    )
    session = Session(
        id=SessionId(uuid.uuid4()),
        engagement_id=engagement_id,
        title="t",
        turn_count=5,
        created_at=now,
        updated_at=now,
    )
    await sessions.create(session)
    for i in range(5):
        await sessions.add_turn(_turn(session.id, i))

    service = AskService(
        engagements=engagements,
        documents=InMemoryDocumentRepository(),
        sessions=sessions,
        vector_index=InMemoryVectorIndex(),
        chat=FakeChatModel(),
        embedder=FakeEmbedder(),
        storage=InMemoryDocumentStorage(),
        settings=settings,
    )
    _session, prior = await service._prepare_session(
        engagement_id=engagement_id,
        question=Question(text="follow-up"),
        session_id=session.id,
    )
    assert len(prior) == 3
    assert [t.ordinal for t in prior] == [2, 3, 4]


def test_session_max_turns_below_context_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(session_context_turns=10, session_max_turns=5)
