from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

UnifiedInterviewOperation = Literal["collect_questions", "deep_research", "practice_session"]


class UnifiedInterviewRequest(BaseModel):
    """Single unified request for interview question collection, research, and practice sessions."""

    operation: UnifiedInterviewOperation

    # Common fields
    company: str = Field(..., min_length=1)
    role: str = Field(default="Software Engineer", min_length=1)

    # Collection-specific
    max_sources: int = Field(default=12, ge=1, le=30)
    max_questions: int = Field(default=60, ge=1, le=200)
    use_firecrawl: bool = Field(
        default=True,
        description="If true, also uses Firecrawl /search alongside SearxNG and DDG.",
    )

    # Research-specific
    include_deep_research: bool = Field(
        default=True, description="If true, includes the company deep research section."
    )
    target_length_words: int = Field(default=1000, ge=300, le=3000)

    # Practice session-specific
    session_id: str | None = None
    candidate_response: str | None = Field(default=None, max_length=20_000)

    # Optional context for better personalization
    candidate_background: str | None = Field(
        default=None,
        description="Optional background/projects context to tailor solutions and practice.",
        max_length=20_000,
    )


class QuestionValidation(BaseModel):
    """LLM-backed validation metadata for a question."""

    is_valid: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class QuestionSolution(BaseModel):
    """Sample solution guidance for an interview question."""

    approach: str
    time_complexity: str | None = None
    space_complexity: str | None = None
    key_insights: list[str] = Field(default_factory=list)


class UnifiedQuestion(BaseModel):
    """Normalized question representation across collectors."""

    question: str
    categories: list[str] = Field(default_factory=list)
    occurrences: int | None = None
    sources: list[str] = Field(default_factory=list)

    validation: QuestionValidation | None = None
    solution: QuestionSolution | None = None


class UnifiedInterviewResponse(BaseModel):
    """Unified response covering all supported interview operations."""

    operation: UnifiedInterviewOperation

    # Question collection results
    questions: list[UnifiedQuestion] | None = None
    sources_scraped: int | None = None

    # Deep research results
    research_report: str | None = None
    key_insights: list[str] | None = None

    # Practice session results
    session_id: str | None = None
    interviewer_response: str | None = None
    feedback: dict[str, Any] | None = None

    # Common metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
