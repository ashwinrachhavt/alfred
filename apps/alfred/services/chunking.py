from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from alfred.schemas.documents import DocumentIngestChunk

_WORD_RE = re.compile(r"\S+")
_SENTENCE_MARKERS = (". ", "? ", "! ", "。", "؟", "!\n", "?\n", ".\n")


@dataclass(frozen=True)
class _WordSpan:
    start: int
    end: int


class ChunkingService:
    """Split cleaned text into overlapping DocumentIngestChunk objects."""

    def chunk(
        self,
        text: str,
        *,
        max_tokens: int = 500,
        overlap: int = 100,
        headings: Optional[list[tuple[int, str]]] = None,
    ) -> List[DocumentIngestChunk]:
        source_text = text or ""
        if not source_text.strip():
            return []

        words = list(self._iter_words(source_text))
        if not words:
            return []

        max_tokens = max(1, max_tokens)
        overlap = max(0, min(overlap, max_tokens - 1))
        total_words = len(words)
        min_chunk = max(1, int(max_tokens * 0.7))
        paragraph_boundaries = self._paragraph_boundaries(source_text, words)
        sentence_boundaries = self._sentence_boundaries(source_text, words)
        heading_list = self._normalize_headings(headings)

        chunks: List[DocumentIngestChunk] = []
        start_idx = 0
        idx = 0

        while start_idx < total_words:
            tentative_end = min(start_idx + max_tokens, total_words)
            end_idx = self._adjust_end_index(
                start_idx,
                tentative_end,
                min_chunk,
                total_words,
                paragraph_boundaries,
                sentence_boundaries,
            )
            end_idx = max(end_idx, start_idx + 1)

            chunk_words = words[start_idx:end_idx]
            char_start = chunk_words[0].start
            char_end = chunk_words[-1].end
            section = self._section_for_span(heading_list, char_start, char_end)
            chunk_text = source_text[char_start:char_end]

            chunks.append(
                DocumentIngestChunk(
                    idx=idx,
                    text=chunk_text,
                    tokens=len(chunk_words),
                    section=section,
                    char_start=char_start,
                    char_end=char_end,
                )
            )

            if end_idx >= total_words:
                break
            start_idx = max(end_idx - overlap, 0)
            idx += 1

        return chunks

    def _iter_words(self, text: str) -> Iterable[_WordSpan]:
        for match in _WORD_RE.finditer(text):
            yield _WordSpan(match.start(), match.end())

    def _paragraph_boundaries(self, text: str, words: Sequence[_WordSpan]) -> set[int]:
        boundaries: set[int] = {0}
        for i in range(1, len(words)):
            gap = text[words[i - 1].end : words[i].start]
            if "\n\n" in gap:
                boundaries.add(i)
        return boundaries

    def _sentence_boundaries(self, text: str, words: Sequence[_WordSpan]) -> set[int]:
        boundaries: set[int] = set()
        for i in range(1, len(words)):
            gap = text[words[i - 1].end : words[i].start]
            if any(marker in gap for marker in _SENTENCE_MARKERS):
                boundaries.add(i)
        return boundaries

    def _adjust_end_index(
        self,
        start_idx: int,
        tentative_end: int,
        min_chunk: int,
        total_words: int,
        paragraph_boundaries: set[int],
        sentence_boundaries: set[int],
    ) -> int:
        if tentative_end >= total_words:
            return total_words
        if tentative_end in paragraph_boundaries:
            return tentative_end

        for boundary_set in (paragraph_boundaries, sentence_boundaries):
            candidate = self._search_backward(boundary_set, tentative_end, start_idx, min_chunk)
            if candidate is not None:
                return candidate
        return tentative_end

    def _search_backward(
        self,
        boundaries: set[int],
        current: int,
        start_idx: int,
        min_chunk: int,
    ) -> Optional[int]:
        candidate = current
        while candidate - start_idx > min_chunk:
            candidate -= 1
            if candidate in boundaries:
                return candidate
        return None

    def _normalize_headings(
        self, headings: Optional[Sequence[Tuple[int, str]]]
    ) -> List[Tuple[int, str]]:
        if not headings:
            return []
        filtered = [(pos, title.strip()) for pos, title in headings if title and pos is not None]
        return sorted(filtered, key=lambda item: item[0])

    def _section_for_span(
        self,
        headings: Sequence[Tuple[int, str]],
        char_start: int,
        char_end: int,
    ) -> Optional[str]:
        section: Optional[str] = None
        for pos, title in headings:
            if pos < char_end:
                section = title
            else:
                break
        return section
