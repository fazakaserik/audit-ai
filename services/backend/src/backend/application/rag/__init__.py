"""RAG: ingest into the vector index and retrieve scored chunks."""

from __future__ import annotations

from backend.application.rag.retrieve import retrieve_relevant_chunks

__all__ = ["retrieve_relevant_chunks"]
