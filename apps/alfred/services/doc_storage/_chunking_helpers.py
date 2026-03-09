"""Chunking helper functions shared across ingestion mixins."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from alfred.models.doc_storage import DocChunkRow
from alfred.services.chunking import ChunkingService
from alfred.services.doc_storage.utils import token_count as _token_count

_CHUNKING_SERVICE = ChunkingService()


def _chunk_payloads_for_text(
    *,
    src_text: str,
    max_tokens: int | None,
    content_type: str,
) -> list[Any]:
    """Chunk text into model-friendly sections for storage.

    Uses a conservative overlap based on the token budget.
    """

    token_budget = int(max_tokens or 0)
    budget = token_budget if token_budget > 0 else 500
    overlap = min(100, int(budget * 0.2))
    return _CHUNKING_SERVICE.chunk(
        src_text,
        max_tokens=budget,
        overlap=overlap,
        content_type=content_type,
        mode="auto",
    )


def _build_doc_chunk_rows(
    *,
    doc_id: uuid.UUID,
    chunk_payloads: list[Any],
    captured_at: datetime,
    captured_hour: int,
    day_bucket: date,
) -> list[DocChunkRow]:
    """Convert chunk payloads into persisted `DocChunkRow` records."""
    rows: list[DocChunkRow] = []
    for ch in chunk_payloads:
        ctokens = ch.tokens if ch.tokens is not None else _token_count(ch.text)
        rows.append(
            DocChunkRow(
                doc_id=doc_id,
                idx=ch.idx,
                text=ch.text,
                tokens=ctokens,
                section=ch.section,
                char_start=ch.char_start,
                char_end=ch.char_end,
                embedding=ch.embedding,
                topics=None,
                captured_at=captured_at,
                captured_hour=captured_hour,
                day_bucket=day_bucket,
            )
        )
    return rows
