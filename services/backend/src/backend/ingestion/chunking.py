"""Structure-aware token chunking for parsed documents."""

from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from backend.ingestion.parsers import ParsedDocument, ParsedSection

_DEFAULT_ENCODING = "cl100k_base"


@dataclass(frozen=True, slots=True)
class Chunk:
    text: str
    heading_path: tuple[str, ...]
    page: int | None
    token_count: int
    ordinal: int


def chunk_document(
    parsed: ParsedDocument,
    *,
    target_tokens: int = 500,
    overlap_ratio: float = 0.15,
) -> list[Chunk]:
    if target_tokens < 1:
        raise ValueError("target_tokens must be at least 1")
    if not 0.0 <= overlap_ratio < 1.0:
        raise ValueError("overlap_ratio must be in [0.0, 1.0)")

    enc = tiktoken.get_encoding(_DEFAULT_ENCODING)
    overlap_tokens = int(target_tokens * overlap_ratio)
    step = max(1, target_tokens - overlap_tokens)

    chunks: list[Chunk] = []
    ordinal = 0
    for section in parsed.sections:
        section_chunks = _chunk_section(
            section,
            enc=enc,
            target_tokens=target_tokens,
            step=step,
        )
        for text, token_count in section_chunks:
            chunks.append(
                Chunk(
                    text=text,
                    heading_path=section.heading_path,
                    page=section.page,
                    token_count=token_count,
                    ordinal=ordinal,
                ),
            )
            ordinal += 1

    return chunks


def _chunk_section(
    section: ParsedSection,
    *,
    enc: tiktoken.Encoding,
    target_tokens: int,
    step: int,
) -> list[tuple[str, int]]:
    body = section.text.strip()
    if not body:
        return []

    tokens = enc.encode(body)
    if not tokens:
        return []

    if len(tokens) <= target_tokens:
        return [(body, len(tokens))]

    windows: list[tuple[str, int]] = []
    start = 0
    while start < len(tokens):
        end = min(start + target_tokens, len(tokens))
        piece = enc.decode(tokens[start:end]).strip()
        if piece:
            windows.append((piece, end - start))
        if end >= len(tokens):
            break
        start += step

    return windows