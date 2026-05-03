from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatOmniboxResult(BaseModel):
    kind: Literal["zettel", "document", "action"]
    id: int | str
    title: str
    topic: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_url: str | None = None
    excerpt: str | None = None
    score: float = 0.0
    action: Literal["search_all", "create_card"] | None = None
    description: str | None = None
    query: str = ""


class ChatOmniboxResponse(BaseModel):
    results: list[ChatOmniboxResult]
