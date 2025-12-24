from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from alfred.core.settings import settings
from alfred.schemas.panel_interview import (
    InterviewerPersona,
    PanelConfig,
    PanelEvent,
    PanelEventType,
    PanelFeedback,
    PanelFeedbackItem,
    PanelMember,
    PanelReaction,
    PanelReactionType,
    PanelSession,
    PanelSessionCreate,
    PanelTurnRequest,
    PanelTurnResponse,
)
from alfred.services.mongo import MongoService


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_personas(config: PanelConfig) -> list[PanelMember]:
    base: list[InterviewerPersona] = [
        InterviewerPersona(
            name="Alex",
            role="Technical Lead",
            personality="detail-oriented",
            focus_areas=["system design", "tradeoffs", "debugging"],
            questioning_style="direct",
            voice="voice_techlead",
            avatar="techlead",
        ),
        InterviewerPersona(
            name="Morgan",
            role="Hiring Manager",
            personality="friendly",
            focus_areas=["leadership", "execution", "collaboration"],
            questioning_style="behavioral",
            voice="voice_manager",
            avatar="manager",
        ),
        InterviewerPersona(
            name="Sam",
            role="HR",
            personality="warm",
            focus_areas=["values", "communication", "motivation"],
            questioning_style="open-ended",
            voice="voice_hr",
            avatar="hr",
        ),
        InterviewerPersona(
            name="Taylor",
            role="Peer Engineer",
            personality="curious",
            focus_areas=["coding", "practical decisions", "teamwork"],
            questioning_style="conversational",
            voice="voice_peer",
            avatar="peer",
        ),
    ]
    personas = config.personas or base[: config.panel_size]
    members: list[PanelMember] = []
    for idx, p in enumerate(personas, start=1):
        members.append(PanelMember(id=str(idx), persona=p))
    return members


@dataclass
class PanelInterviewService:
    """Simplified panel interview service backed by Postgres JSONB store."""

    collection_name: str = settings.panel_interview_sessions_collection
    _store: MongoService | None = None

    def __post_init__(self) -> None:
        self._store = MongoService(default_collection=self.collection_name)

    def ensure_indexes(self) -> None:
        return

    # --------------- Sessions ---------------
    def create_session(self, payload: PanelSessionCreate) -> PanelSession:
        config = payload.config
        members = _default_personas(config)
        now = _utcnow_iso()
        session_id = uuid.uuid4().hex

        session = PanelSession(
            id=session_id,
            config=config,
            members=members,
            status="active",
            created_at=now,
            updated_at=now,
            turn_index=0,
            time_remaining_s=int(config.total_minutes) * 60,
            current_speaker_id=None,
            transcript=[],
        )
        doc = session.model_dump(mode="json")
        doc["_id"] = session_id
        self._store.insert_one(doc)
        return session

    def get_session(self, session_id: str) -> PanelSession:
        doc = self._store.find_one({"_id": session_id})
        if not doc:
            raise ValueError("Session not found")
        doc["id"] = str(doc.pop("_id", session_id))
        return PanelSession.model_validate(doc)

    def pause(self, session_id: str) -> PanelSession:
        now = _utcnow_iso()
        self._store.update_one(
            {"_id": session_id}, {"$set": {"status": "paused", "updated_at": now}}
        )
        return self.get_session(session_id)

    def resume(self, session_id: str) -> PanelSession:
        now = _utcnow_iso()
        self._store.update_one(
            {"_id": session_id}, {"$set": {"status": "active", "updated_at": now}}
        )
        return self.get_session(session_id)

    # --------------- Turns ---------------
    def submit_turn(self, session_id: str, payload: PanelTurnRequest) -> PanelTurnResponse:
        session = self.get_session(session_id)
        now = _utcnow_iso()
        evt_answer = PanelEvent(
            type=PanelEventType.answer,
            timestamp=now,
            member_id=None,
            text=payload.answer,
            reactions=[],
            meta={},
        )
        evt_question = PanelEvent(
            type=PanelEventType.question,
            timestamp=now,
            member_id=session.members[0].id if session.members else None,
            text="Can you elaborate on the biggest challenge you faced?",
            reactions=[
                PanelReaction(member_id=session.members[0].id, reaction=PanelReactionType.neutral)
            ]
            if session.members
            else [],
            meta={},
        )
        session.transcript.extend([evt_answer, evt_question])
        session.updated_at = now
        session.turn_index += 1
        self._store.update_one({"_id": session_id}, {"$set": session.model_dump(mode="json")})
        return PanelTurnResponse(session=session, events=[evt_answer, evt_question])

    def _load_question_bank(self, session_id: str) -> list[str]:
        doc = self._store.find_one({"_id": session_id}, projection={"question_bank": 1})
        bank = (doc or {}).get("question_bank")
        if isinstance(bank, list):
            return [q for q in bank if isinstance(q, str) and q.strip()]
        return []

    # --------------- Feedback ---------------
    def feedback(self, session_id: str) -> PanelFeedback:
        session = self.get_session(session_id)
        return PanelFeedback(
            session_id=session_id,
            overall_summary="Session feedback is not yet generated.",
            overall_score=None,
            by_member=[
                PanelFeedbackItem(
                    member_id=m.id, strengths=[], improvements=[], score=None, summary=None
                )
                for m in session.members
            ],
        )


__all__ = ["PanelInterviewService"]
