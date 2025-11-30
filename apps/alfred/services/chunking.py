from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from alfred.schemas.documents import DocumentIngestChunk


def _safe_imports():
    try:
        from langchain_text_splitters import (
            CharacterTextSplitter,
            RecursiveCharacterTextSplitter,
        )
    except Exception:  # pragma: no cover - optional dep
        CharacterTextSplitter = None  # type: ignore[assignment]
        RecursiveCharacterTextSplitter = None  # type: ignore[assignment]
    try:
        from langchain_text_splitters import MarkdownHeaderTextSplitter
    except Exception:  # pragma: no cover - optional dep
        MarkdownHeaderTextSplitter = None  # type: ignore[assignment]
    try:
        from langchain_text_splitters import HTMLHeaderTextSplitter
    except Exception:  # pragma: no cover - optional dep
        HTMLHeaderTextSplitter = None  # type: ignore[assignment]
    return (
        CharacterTextSplitter,
        RecursiveCharacterTextSplitter,
        MarkdownHeaderTextSplitter,
        HTMLHeaderTextSplitter,
    )


def _count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    try:
        import tiktoken

        enc = tiktoken.get_encoding(encoding_name)
        return len(enc.encode(text or ""))
    except Exception:
        return len((text or "").split())


@dataclass
class ChunkingService:
    """Chunk text using LangChain text splitters.

    Modes:
    - recursive (default): RecursiveCharacterTextSplitter
    - token: CharacterTextSplitter.from_tiktoken_encoder
    - markdown: MarkdownHeaderTextSplitter (falls back to recursive)
    - html: HTMLHeaderTextSplitter (falls back to recursive)
    """

    def chunk(
        self,
        text: str,
        *,
        max_tokens: int = 500,
        overlap: int = 100,
        mode: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> List[DocumentIngestChunk]:
        src = (text or "").strip()
        if not src:
            return []

        (
            CharacterTextSplitter,
            RecursiveCharacterTextSplitter,
            MarkdownHeaderTextSplitter,
            HTMLHeaderTextSplitter,
        ) = _safe_imports()

        chosen = (mode or "").strip().lower()
        if not chosen or chosen == "auto":
            if (content_type or "").lower() == "markdown" or src.startswith("#"):
                chosen = "markdown"
            else:
                chosen = "recursive"

        if chosen == "markdown" and MarkdownHeaderTextSplitter is not None:
            splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
                strip_headers=False,
            )
            docs = splitter.split_text(src)
            chunks: List[DocumentIngestChunk] = []
            for idx, d in enumerate(docs):
                content = d.page_content or ""
                # Best-effort section extraction from first header line
                first_line = (content.splitlines() or [""])[0]
                section = first_line.strip().lstrip("# ") if first_line.startswith("#") else None
                chunks.append(
                    DocumentIngestChunk(
                        idx=idx,
                        text=content,
                        tokens=_count_tokens(content),
                        section=section,
                        char_start=None,
                        char_end=None,
                    )
                )
            return chunks

        if chosen == "html" and HTMLHeaderTextSplitter is not None:
            docs = HTMLHeaderTextSplitter().split_text(src)
            out: List[DocumentIngestChunk] = []
            for idx, d in enumerate(docs):
                content = d.page_content or ""
                out.append(
                    DocumentIngestChunk(
                        idx=idx,
                        text=content,
                        tokens=_count_tokens(content),
                        section=None,
                        char_start=None,
                        char_end=None,
                    )
                )
            return out

        if chosen == "token" and CharacterTextSplitter is not None:
            splitter = CharacterTextSplitter.from_tiktoken_encoder(
                encoding_name="cl100k_base", chunk_size=max_tokens, chunk_overlap=max(0, overlap)
            )
            parts = splitter.split_text(src)
            return [
                DocumentIngestChunk(
                    idx=i,
                    text=part,
                    tokens=_count_tokens(part),
                    section=None,
                    char_start=None,
                    char_end=None,
                )
                for i, part in enumerate(parts)
            ]

        # default recursive fallback
        if RecursiveCharacterTextSplitter is None:  # pragma: no cover - optional dep
            parts = _fallback_split(src, max_tokens, overlap)
        else:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=max_tokens, chunk_overlap=max(0, overlap)
            )
            parts = splitter.split_text(src)
        return [
            DocumentIngestChunk(
                idx=i,
                text=part,
                tokens=_count_tokens(part),
                section=None,
                char_start=None,
                char_end=None,
            )
            for i, part in enumerate(parts)
        ]


def _fallback_split(text: str, max_tokens: int, overlap: int) -> List[str]:
    """Very small local fallback if langchain splitters unavailable."""
    words = (text or "").split()
    if not words:
        return []
    max_tokens = max(1, max_tokens)
    overlap = max(0, min(overlap, max_tokens - 1))
    parts: List[str] = []
    i = 0
    while i < len(words):
        j = min(i + max_tokens, len(words))
        parts.append(" ".join(words[i:j]))
        if j >= len(words):
            break
        i = max(j - overlap, 0)
    return parts
