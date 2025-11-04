"""Utilities for loading prompt templates from disk."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def load_prompt(*relative_parts: str) -> str:
    """Load a prompt template from ``apps/alfred/prompts``.

    Args:
        *relative_parts: Path segments under the prompts package, e.g. ("agentic_rag", "core.md").

    Returns:
        The prompt text with surrounding whitespace removed.
    """

    path = _PROMPTS_ROOT.joinpath(*relative_parts)
    if not path.exists():  # pragma: no cover - guard for missing assets
        raise FileNotFoundError(f"Prompt template missing: {path}")
    return path.read_text(encoding="utf-8").strip()


__all__ = ["load_prompt"]
