from __future__ import annotations

from typing import Any, TypedDict

from alfred.schemas.unified_interview import UnifiedInterviewOperation


class InterviewAgentState(TypedDict):
    operation: UnifiedInterviewOperation
    company: str
    role: str
    max_sources: int
    max_questions: int
    use_firecrawl: bool
    include_deep_research: bool
    target_length_words: int
    candidate_background: str | None
    candidate_response: str | None
    session_id: str | None

    raw_questions: list[dict[str, Any]]
    validated_questions: list[dict[str, Any]]
    questions_with_solutions: list[dict[str, Any]]
    sources_scraped: int

    company_research: dict[str, Any]
    research_report: str

    practice_events: list[dict[str, Any]]
    errors: list[str]
