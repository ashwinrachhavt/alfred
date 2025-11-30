from __future__ import annotations

import re


class TextCleaningService:
    """Normalize raw text prior to chunking or ingestion."""

    _collapse_whitespace = re.compile(r"[ \t]+")
    _collapse_newlines = re.compile(r"\n{3,}")

    def clean(self, text: str) -> str:
        payload = text or ""
        payload = payload.replace("\r\n", "\n").replace("\r", "\n")
        payload = self._collapse_whitespace.sub(" ", payload)
        payload = self._collapse_newlines.sub("\n\n", payload)
        return payload.strip()
