"""Ask session binding protocol."""

from __future__ import annotations

from typing import Protocol

from backend.application.repositories.document import DocumentRepository
from backend.application.repositories.engagement import EngagementRepository
from backend.application.repositories.session import SessionRepository
from backend.application.storage.vector_index import VectorIndex


class AskSessionBound(Protocol):
    """Engagement/session/vector/document ports needed by ask_question (avoids bootstrap import)."""

    @property
    def engagements(self) -> EngagementRepository: ...

    @property
    def documents(self) -> DocumentRepository: ...

    @property
    def sessions(self) -> SessionRepository: ...

    @property
    def vector_index(self) -> VectorIndex: ...
