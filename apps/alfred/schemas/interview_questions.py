from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QuestionSource(BaseModel):
    """Raw source plus extracted question snippets."""

    url: str | None = Field(default=None, description="Source URL")
    title: str | None = Field(default=None, description="SERP or page title")
    snippet: str | None = Field(default=None, description="Search snippet or summary")
    provider: str | None = Field(default=None, description="Search provider identifier")
    questions: list[str] = Field(
        default_factory=list, description="Questions extracted from the page"
    )
    error: str | None = Field(default=None, description="Any scrape error encountered")


class QuestionItem(BaseModel):
    """A single normalized interview question plus aggregates."""

    question: str
    categories: list[str] = Field(
        default_factory=list, description="Heuristic tags such as coding/system_design"
    )
    occurrences: int = Field(default=1, description="How many sources contained this question")
    sources: list[str] = Field(default_factory=list, description="URLs where the question was seen")


class InterviewQuestionsReport(BaseModel):
    """High-signal interview question rollup for a company/role."""

    company: str
    role: str | None = None
    queries: list[str] = Field(
        default_factory=list, description="Queries issued to search providers"
    )
    total_unique_questions: int
    questions: list[QuestionItem]
    sources: list[QuestionSource]
    warnings: list[str] = Field(default_factory=list)
    meta: dict[str, Any] | None = None
