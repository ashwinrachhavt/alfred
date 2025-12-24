from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StarStory(BaseModel):
    """A STAR story used in interview preparation."""

    title: Optional[str] = None
    situation: str
    task: str
    action: str
    result: str
    skills: List[str] = Field(default_factory=list)


class LikelyQuestion(BaseModel):
    """A likely interview question with a suggested answer."""

    question: str
    suggested_answer: str
    focus_areas: List[str] = Field(default_factory=list)


class TechnicalTopic(BaseModel):
    """A technical topic to refresh with a relative priority."""

    topic: str
    priority: int = Field(default=3, ge=1, le=5)
    notes: Optional[str] = None
    resources: List[str] = Field(default_factory=list)


class PrepDoc(BaseModel):
    """The structured 5-section prep document."""

    company_overview: str = ""
    role_analysis: str = ""
    star_stories: List[StarStory] = Field(default_factory=list)
    likely_questions: List[LikelyQuestion] = Field(default_factory=list)
    technical_topics: List[TechnicalTopic] = Field(default_factory=list)


class QuizQuestion(BaseModel):
    """A quiz question used for practice."""

    question: str
    answer: Optional[str] = None
    choices: Optional[List[str]] = None
    tags: List[str] = Field(default_factory=list)


class QuizAttempt(BaseModel):
    """A single quiz attempt with scoring and answer capture."""

    taken_at: datetime
    score: float = Field(ge=0, le=1)
    answers: Dict[str, Any] = Field(default_factory=dict)


class InterviewQuiz(BaseModel):
    """Quiz container stored under an interview prep record."""

    questions: List[QuizQuestion] = Field(default_factory=list)
    score: Optional[float] = Field(default=None, ge=0, le=1)
    attempts: List[QuizAttempt] = Field(default_factory=list)


class InterviewReminders(BaseModel):
    """Reminder delivery state for an interview prep record."""

    start_prep_sent_at: Optional[datetime] = None
    review_sent_at: Optional[datetime] = None
    checklist_sent_at: Optional[datetime] = None
    final_checklist_sent_at: Optional[datetime] = None


class InterviewChecklist(BaseModel):
    """Day-of checklist generated for an interview."""

    markdown: str
    timeline: List[str] = Field(default_factory=list)
    talking_points: List[str] = Field(default_factory=list)
    questions_to_ask: List[str] = Field(default_factory=list)
    setup: List[str] = Field(default_factory=list)
    mindset: List[str] = Field(default_factory=list)


class InterviewFeedback(BaseModel):
    """Post-interview feedback captured from the user."""

    helpful_materials: List[str] = Field(default_factory=list)
    actual_questions: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class InterviewCalendarEvent(BaseModel):
    """Calendar event metadata for the scheduled interview."""

    event_id: str
    event_link: Optional[str] = None
    meet_link: Optional[str] = None
    created_at: Optional[datetime] = None


class InterviewPrepRecord(BaseModel):
    """Canonical Mongo record for `interview_preps`.

    This model is intended for validating DB records (allows `_id` and extra keys).
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    job_application_id: Optional[str] = None
    company: str
    role: str
    interview_date: Optional[datetime] = None
    interview_type: Optional[str] = None

    prep_doc: PrepDoc = Field(default_factory=PrepDoc)
    prep_markdown: Optional[str] = None
    prep_markdown_generated_at: Optional[datetime] = None
    quiz: InterviewQuiz = Field(default_factory=InterviewQuiz)

    performance_rating: Optional[int] = Field(default=None, ge=1, le=10)
    confidence_rating: Optional[int] = Field(default=None, ge=1, le=10)
    generated_at: Optional[datetime] = None
    source: Optional[Dict[str, Any]] = None
    reminders: InterviewReminders = Field(default_factory=InterviewReminders)
    checklist: Optional[InterviewChecklist] = None
    checklist_generated_at: Optional[datetime] = None
    feedback: Optional[InterviewFeedback] = None
    calendar_event: Optional[InterviewCalendarEvent] = None

    @field_validator("company", "role")
    @classmethod
    def _non_empty_str(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("must be non-empty")
        return v.strip()


class InterviewPrepCreate(BaseModel):
    """Create payload for an interview prep record."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    job_application_id: Optional[str] = None
    company: str
    role: str
    interview_date: Optional[datetime] = None
    interview_type: Optional[str] = None
    source: Optional[Dict[str, Any]] = None

    @field_validator("company", "role")
    @classmethod
    def _non_empty_str(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("must be non-empty")
        return v.strip()


class InterviewPrepUpdate(BaseModel):
    """Patch payload for an interview prep record."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    interview_date: Optional[datetime] = None
    interview_type: Optional[str] = None
    prep_doc: Optional[PrepDoc] = None
    prep_markdown: Optional[str] = None
    prep_markdown_generated_at: Optional[datetime] = None
    quiz: Optional[InterviewQuiz] = None
    performance_rating: Optional[int] = Field(default=None, ge=1, le=10)
    confidence_rating: Optional[int] = Field(default=None, ge=1, le=10)
    generated_at: Optional[datetime] = None
    source: Optional[Dict[str, Any]] = None
    reminders: Optional[InterviewReminders] = None
    checklist: Optional[InterviewChecklist] = None
    checklist_generated_at: Optional[datetime] = None
    feedback: Optional[InterviewFeedback] = None
    calendar_event: Optional[InterviewCalendarEvent] = None


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
