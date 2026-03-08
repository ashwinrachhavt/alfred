from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StarStory(BaseModel):
    """A STAR story used in interview preparation."""

    title: str | None = None
    situation: str
    task: str
    action: str
    result: str
    skills: list[str] = Field(default_factory=list)


class LikelyQuestion(BaseModel):
    """A likely interview question with a suggested answer."""

    question: str
    suggested_answer: str
    focus_areas: list[str] = Field(default_factory=list)


class TechnicalTopic(BaseModel):
    """A technical topic to refresh with a relative priority."""

    topic: str
    priority: int = Field(default=3, ge=1, le=5)
    notes: str | None = None
    resources: list[str] = Field(default_factory=list)


class PrepDoc(BaseModel):
    """The structured 5-section prep document."""

    company_overview: str = ""
    role_analysis: str = ""
    star_stories: list[StarStory] = Field(default_factory=list)
    likely_questions: list[LikelyQuestion] = Field(default_factory=list)
    technical_topics: list[TechnicalTopic] = Field(default_factory=list)


class QuizQuestion(BaseModel):
    """A quiz question used for practice."""

    question: str
    answer: str | None = None
    choices: list[str] | None = None
    tags: list[str] = Field(default_factory=list)


class QuizAttempt(BaseModel):
    """A single quiz attempt with scoring and answer capture."""

    taken_at: datetime
    score: float = Field(ge=0, le=1)
    answers: dict[str, Any] = Field(default_factory=dict)


class InterviewQuiz(BaseModel):
    """Quiz container stored under an interview prep record."""

    questions: list[QuizQuestion] = Field(default_factory=list)
    score: float | None = Field(default=None, ge=0, le=1)
    attempts: list[QuizAttempt] = Field(default_factory=list)


class InterviewReminders(BaseModel):
    """Reminder delivery state for an interview prep record."""

    start_prep_sent_at: datetime | None = None
    review_sent_at: datetime | None = None
    checklist_sent_at: datetime | None = None
    final_checklist_sent_at: datetime | None = None


class InterviewChecklist(BaseModel):
    """Day-of checklist generated for an interview."""

    markdown: str
    timeline: list[str] = Field(default_factory=list)
    talking_points: list[str] = Field(default_factory=list)
    questions_to_ask: list[str] = Field(default_factory=list)
    setup: list[str] = Field(default_factory=list)
    mindset: list[str] = Field(default_factory=list)


class InterviewFeedback(BaseModel):
    """Post-interview feedback captured from the user."""

    helpful_materials: list[str] = Field(default_factory=list)
    actual_questions: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    notes: str | None = None


class InterviewCalendarEvent(BaseModel):
    """Calendar event metadata for the scheduled interview."""

    event_id: str
    event_link: str | None = None
    meet_link: str | None = None
    created_at: datetime | None = None


class InterviewPrepRecord(BaseModel):
    """Canonical Mongo record for `interview_preps`.

    This model is intended for validating DB records (allows `_id` and extra keys).
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    job_application_id: str | None = None
    company: str
    role: str
    interview_date: datetime | None = None
    interview_type: str | None = None

    prep_doc: PrepDoc = Field(default_factory=PrepDoc)
    prep_markdown: str | None = None
    prep_markdown_generated_at: datetime | None = None
    quiz: InterviewQuiz = Field(default_factory=InterviewQuiz)

    performance_rating: int | None = Field(default=None, ge=1, le=10)
    confidence_rating: int | None = Field(default=None, ge=1, le=10)
    generated_at: datetime | None = None
    source: dict[str, Any] | None = None
    reminders: InterviewReminders = Field(default_factory=InterviewReminders)
    checklist: InterviewChecklist | None = None
    checklist_generated_at: datetime | None = None
    feedback: InterviewFeedback | None = None
    calendar_event: InterviewCalendarEvent | None = None

    @field_validator("company", "role")
    @classmethod
    def _non_empty_str(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("must be non-empty")
        return v.strip()


class InterviewPrepCreate(BaseModel):
    """Create payload for an interview prep record."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    job_application_id: str | None = None
    company: str
    role: str
    interview_date: datetime | None = None
    interview_type: str | None = None
    source: dict[str, Any] | None = None

    @field_validator("company", "role")
    @classmethod
    def _non_empty_str(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("must be non-empty")
        return v.strip()


class InterviewPrepUpdate(BaseModel):
    """Patch payload for an interview prep record."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    interview_date: datetime | None = None
    interview_type: str | None = None
    prep_doc: PrepDoc | None = None
    prep_markdown: str | None = None
    prep_markdown_generated_at: datetime | None = None
    quiz: InterviewQuiz | None = None
    performance_rating: int | None = Field(default=None, ge=1, le=10)
    confidence_rating: int | None = Field(default=None, ge=1, le=10)
    generated_at: datetime | None = None
    source: dict[str, Any] | None = None
    reminders: InterviewReminders | None = None
    checklist: InterviewChecklist | None = None
    checklist_generated_at: datetime | None = None
    feedback: InterviewFeedback | None = None
    calendar_event: InterviewCalendarEvent | None = None

__all__ = [
    "InterviewPrepCreate",
    "InterviewChecklist",
    "InterviewFeedback",
    "InterviewCalendarEvent",
    "InterviewPrepRecord",
    "InterviewPrepUpdate",
    "InterviewQuiz",
    "InterviewReminders",
    "LikelyQuestion",
    "PrepDoc",
    "QuizAttempt",
    "QuizQuestion",
    "StarStory",
    "TechnicalTopic",
]
