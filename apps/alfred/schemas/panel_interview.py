from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class PanelDifficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"
    expert = "expert"


class PanelEventType(str, Enum):
    question = "question"
    follow_up = "follow_up"
    interruption = "interruption"
    answer = "answer"
    reaction = "reaction"
    note = "note"


class PanelReactionType(str, Enum):
    nodding = "nodding"
    confused = "confused"
    interested = "interested"
    skeptical = "skeptical"
    impressed = "impressed"
    concerned = "concerned"
    neutral = "neutral"


class InterviewerPersona(BaseModel):
    """Configuration for a single interviewer persona."""

    role: str = Field(
        ..., description='e.g., "Technical Lead", "Hiring Manager", "HR", "Peer Engineer"'
    )
    personality: str = Field(..., description='e.g., "skeptical", "friendly", "detail-oriented"')
    focus_areas: list[str] = Field(
        default_factory=list, description='e.g., ["system design", "leadership"]'
    )
    questioning_style: str = Field(..., description='e.g., "direct", "open-ended", "behavioral"')

    name: Optional[str] = Field(default=None, description="Display name for the persona.")
    voice: Optional[str] = Field(
        default=None,
        description="Voice identifier for TTS clients (frontend chooses the actual provider/voice mapping).",
    )
    avatar: Optional[str] = Field(
        default=None,
        description="Avatar identifier (frontend mapping) for visual rendering.",
    )


class PanelConfig(BaseModel):
    """Configuration for a panel interview session."""

    company: Optional[str] = Field(default=None, description="Company name for realism (optional).")
    role: Optional[str] = Field(
        default=None, description="Target role for the interview (optional)."
    )
    difficulty: PanelDifficulty = Field(default=PanelDifficulty.medium)

    panel_size: int = Field(default=4, ge=3, le=5)
    personas: list[InterviewerPersona] = Field(
        default_factory=list,
        description="Optional explicit personas; if empty, defaults are generated from difficulty.",
    )

    # Dynamics knobs
    allow_interruptions: bool = Field(default=True)
    time_pressure: bool = Field(default=True)
    total_minutes: int = Field(default=30, ge=5, le=90)

    # Realism knobs
    include_company_question_bank: bool = Field(
        default=True,
        description="If enabled, uses stored company interview experiences as a question bank (when available).",
    )
    max_company_questions: int = Field(default=25, ge=0, le=200)


class PanelMember(BaseModel):
    """A concrete panel member for a session (persona + stable id)."""

    id: str
    persona: InterviewerPersona


class PanelReaction(BaseModel):
    member_id: str
    reaction: PanelReactionType = Field(default=PanelReactionType.neutral)
    note: Optional[str] = Field(
        default=None, description="Short reaction note for UI (e.g., 'wants more detail')."
    )


class PanelEvent(BaseModel):
    type: PanelEventType
    timestamp: str = Field(..., description="UTC ISO timestamp")

    member_id: Optional[str] = Field(
        default=None, description="Speaker or reactor id, when applicable."
    )
    text: Optional[str] = Field(
        default=None, description="Utterance text for question/answer/follow-up."
    )

    reactions: list[PanelReaction] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class PanelSession(BaseModel):
    id: str
    config: PanelConfig
    members: list[PanelMember]
    status: str = Field(default="active", description="active | paused | completed")
    created_at: str
    updated_at: str

    # Session state
    turn_index: int = 0
    time_remaining_s: int = 0
    current_speaker_id: Optional[str] = None

    transcript: list[PanelEvent] = Field(default_factory=list)


class PanelSessionCreate(BaseModel):
    config: PanelConfig
    # Optional context to tailor questions (resume snippet, user background, etc.)
    candidate_context: Optional[str] = Field(default=None, max_length=20_000)


class PanelTurnRequest(BaseModel):
    answer: str = Field(
        ..., description="Candidate answer to the last question.", max_length=20_000
    )


class PanelTurnResponse(BaseModel):
    session: PanelSession
    events: list[PanelEvent] = Field(
        default_factory=list, description="Newly generated events for this turn."
    )


class PanelFeedbackItem(BaseModel):
    member_id: str
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    score: int | None = Field(default=None, ge=1, le=10)
    summary: Optional[str] = None


class PanelFeedback(BaseModel):
    session_id: str
    overall_summary: str
    overall_score: int | None = Field(default=None, ge=1, le=10)
    by_member: list[PanelFeedbackItem] = Field(default_factory=list)
