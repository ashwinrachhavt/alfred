"""Typed state definitions for the research LangGraph."""

from __future__ import annotations

from typing import Literal, TypedDict

ArticleTone = Literal["neutral", "casual", "technical"]


class ResearchSource(TypedDict, total=False):
    title: str
    url: str
    snippet: str
    content: str
    source_type: Literal["web", "internal"]


class ResearchState(TypedDict, total=False):
    query: str
    target_length_words: int
    tone: ArticleTone

    expanded_queries: list[str]
    subtopics: list[str]

    sources: list[ResearchSource]
    evidence_notes: str

    outline: str
    draft: str
    revision_instructions: str
    final_article: str
