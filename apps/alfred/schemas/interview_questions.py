from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class QuestionSource(BaseModel):
    """Raw source plus extracted question snippets."""

    url: Optional[str] = Field(default=None, description="Source URL")
    title: Optional[str] = Field(default=None, description="SERP or page title")
    snippet: Optional[str] = Field(default=None, description="Search snippet or summary")
    provider: Optional[str] = Field(default=None, description="Search provider identifier")
    questions: List[str] = Field(
        default_factory=list, description="Questions extracted from the page"
    )
    error: Optional[str] = Field(default=None, description="Any scrape error encountered")


class QuestionItem(BaseModel):
    """A single normalized interview question plus aggregates."""

    question: str
    categories: List[str] = Field(
        default_factory=list, description="Heuristic tags such as coding/system_design"
    )
    occurrences: int = Field(default=1, description="How many sources contained this question")
    sources: List[str] = Field(default_factory=list, description="URLs where the question was seen")


class InterviewQuestionsReport(BaseModel):
    """High-signal interview question rollup for a company/role."""

    company: str
    role: Optional[str] = None
    queries: List[str] = Field(
        default_factory=list, description="Queries issued to search providers"
    )
    total_unique_questions: int
    questions: List[QuestionItem]
    sources: List[QuestionSource]
    warnings: List[str] = Field(default_factory=list)
    meta: dict[str, Any] | None = None
