"""Known embedding model dimensions (adapter-local lookup)."""

from __future__ import annotations

EMBEDDING_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "nomic-embed-text": 768,
}


def dimensions_for(model_name: str) -> int:
    dims = EMBEDDING_DIMENSIONS.get(model_name)
    if dims is None:
        msg = f"unknown embedding model dimensions for {model_name!r}"
        raise ValueError(msg)
    return dims
