"""LangGraph email + calendar agent helpers."""

from __future__ import annotations

from functools import lru_cache

from alfred.prompts import load_prompt

_SYSTEM_PROMPT_PATH = ("email_calendar_agent", "system.md")


@lru_cache(maxsize=1)
def get_email_calendar_system_prompt() -> str:
    """Return the system prompt string for the email+calendar LangGraph agent."""

    return load_prompt(*_SYSTEM_PROMPT_PATH)


__all__ = ["get_email_calendar_system_prompt"]
