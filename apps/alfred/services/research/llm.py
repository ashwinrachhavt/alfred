"""LLM helpers for research workflows."""

from __future__ import annotations

from functools import cache

from langchain_openai import ChatOpenAI

from alfred.services.company_researcher import make_llm as _base_make_llm


@cache
def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    """Return a cached OpenAI chat model with the desired temperature."""
    return _base_make_llm(temperature=temperature)
