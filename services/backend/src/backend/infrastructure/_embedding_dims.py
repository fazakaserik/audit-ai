"""Known embedding model dimensions (adapter-local lookup)."""

from __future__ import annotations

from backend.infrastructure.llm.litellm_models import bare_model_name

EMBEDDING_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "nomic-embed-text": 768,
}


def dimensions_for(model_name: str, *, override: int | None = None) -> int:
    if override is not None:
        return override
    candidates = (model_name, bare_model_name(model_name) if "/" in model_name else model_name)
    for candidate in candidates:
        dims = EMBEDDING_DIMENSIONS.get(candidate)
        if dims is not None:
            return dims
    msg = (
        f"unknown embedding model dimensions for {model_name!r}; "
        "set EMBEDDING_DIMENSIONS or add the model to the known-dims table"
    )
    raise ValueError(msg)
