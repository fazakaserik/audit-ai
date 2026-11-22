"""Unit tests for domain feature models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from domain.answer import (
    Answered,
    Citation,
    InsufficientEvidence,
    InsufficientReason,
    Question,
    SuggestedClientQuestion,
)
from domain.document import DocumentId, DocumentPath
from domain.engagement import EngagementId
from domain.passage import PassageId


def test_question_strips_and_rejects_blank() -> None:
    q = Question(text="  hello  ")
    assert q.text == "hello"
    with pytest.raises(ValidationError):
        Question(text="   ")


def test_engagement_id_validation() -> None:
    adapter = TypeAdapter(EngagementId)
    assert adapter.validate_python("northwind-fy2025") == "northwind-fy2025"
    with pytest.raises(ValidationError):
        adapter.validate_python("Bad_Id")
    with pytest.raises(ValidationError):
        adapter.validate_python("a")


def test_document_path_rejects_traversal() -> None:
    adapter = TypeAdapter(DocumentPath)
    assert adapter.validate_python("contracts/a.pdf") == "contracts/a.pdf"
    with pytest.raises(ValidationError):
        adapter.validate_python("../secret.txt")
    with pytest.raises(ValidationError):
        adapter.validate_python("/abs/file.txt")


def test_answered_requires_citation() -> None:
    citation = Citation(
        marker=1,
        passage_id=PassageId(uuid.uuid4()),
        document_id=DocumentId(uuid.uuid4()),
        document_path="contracts/a.pdf",
        snippet="payment within 30 days",
        score=0.9,
    )
    answered = Answered(text="Terms are 30 days [1]", citations=(citation,))
    assert answered.status == "answered"
    with pytest.raises(ValidationError):
        Answered(text="no cite", citations=())


def test_insufficient_requires_suggestions() -> None:
    with pytest.raises(ValidationError):
        InsufficientEvidence(
            reason=InsufficientReason.NO_RELEVANT_PASSAGES,
            suggested_client_questions=(),
        )
    result = InsufficientEvidence(
        reason=InsufficientReason.NO_RELEVANT_PASSAGES,
        suggested_client_questions=(
            SuggestedClientQuestion(
                question="Please provide the lease agreement.",
                rationale="No lease documents were found.",
            ),
        ),
    )
    assert result.status == "insufficient_evidence"


def test_timestamps_are_timezone_aware() -> None:
    now = datetime.now(UTC)
    assert now.tzinfo is not None
