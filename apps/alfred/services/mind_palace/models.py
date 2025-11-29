from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

SelectionType = Literal["full_page", "selection", "article_only"]


@dataclass
class PageInput:
    raw_text: str
    html: str | None = None
    page_url: str | None = None
    page_title: str | None = None
    selection_type: SelectionType = "full_page"
    user_id: str | None = None


@dataclass
class PageResult:
    id: str
    status: str


@dataclass
class Hyperlink:
    url: str
    text: str | None
    is_internal: bool
    position: int | None


@dataclass
class EnrichmentResult:
    topic_category: str | None
    summary: str | None
    highlights: list[dict[str, Any]]
    insights: list[dict[str, Any]]
    domain_summary: str | None
    tags: list[str]
    topic_graph: dict[str, Any]
    model_name: str | None
    prompt_version: str
    temperature: float | None


__all__ = [
    "SelectionType",
    "PageInput",
    "PageResult",
    "Hyperlink",
    "EnrichmentResult",
]
