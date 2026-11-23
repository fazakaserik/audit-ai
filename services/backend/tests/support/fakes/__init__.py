"""In-memory fakes for application Protocols (offline unit/api tests)."""

from __future__ import annotations

from .llm import (
    FakeChatModel,
    FakeEmbedder,
    agent_search_tool_turns,
    repeat_agent_search_tool_turns,
)
from .repos import (
    InMemoryDocumentRepository,
    InMemoryEngagementRepository,
    InMemoryJobQueue,
    InMemorySessionRepository,
    InMemoryUploadRepository,
    NoopJobQueue,
)
from .storage import InMemoryDocumentStorage
from .vector import InMemoryVectorIndex

__all__ = [
    "FakeChatModel",
    "FakeEmbedder",
    "InMemoryDocumentRepository",
    "InMemoryDocumentStorage",
    "InMemoryEngagementRepository",
    "InMemoryJobQueue",
    "InMemorySessionRepository",
    "InMemoryUploadRepository",
    "InMemoryVectorIndex",
    "NoopJobQueue",
    "agent_search_tool_turns",
    "repeat_agent_search_tool_turns",
]
