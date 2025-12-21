from __future__ import annotations

import logging
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database

from alfred.core.exceptions import ServiceUnavailableError
from alfred.core.settings import settings
from alfred.schemas.panel_interview import (
    InterviewerPersona,
    PanelConfig,
    PanelDifficulty,
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

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _compact(text: str | None) -> str:
    return " ".join((text or "").split()).strip()


def _clamp_int(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(val)))


def _default_personas(difficulty: PanelDifficulty, *, panel_size: int) -> list[InterviewerPersona]:
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
            personality="skeptical"
            if difficulty in {PanelDifficulty.hard, PanelDifficulty.expert}
            else "friendly",
            focus_areas=["leadership", "execution", "collaboration"],
            questioning_style="behavioral",
            voice="voice_manager",
            avatar="manager",
        ),
        InterviewerPersona(
            name="Sam",
            role="HR",
            personality="warm" if difficulty == PanelDifficulty.easy else "neutral",
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
        InterviewerPersona(
            name="Jordan",
            role="Cross-functional Partner",
            personality="probing" if difficulty == PanelDifficulty.expert else "pragmatic",
            focus_areas=["stakeholders", "product sense", "ambiguity"],
            questioning_style="scenario-based",
            voice="voice_partner",
            avatar="partner",
        ),
    ]
    return base[:panel_size]


def _difficulty_profile(difficulty: PanelDifficulty) -> dict[str, float]:
    # Controls the "feel" of the interview.
    if difficulty == PanelDifficulty.easy:
        return {"interrupt_p": 0.05, "followup_p": 0.35, "pressure": 0.10}
    if difficulty == PanelDifficulty.medium:
        return {"interrupt_p": 0.10, "followup_p": 0.50, "pressure": 0.25}
    if difficulty == PanelDifficulty.hard:
        return {"interrupt_p": 0.18, "followup_p": 0.65, "pressure": 0.45}
    return {"interrupt_p": 0.25, "followup_p": 0.75, "pressure": 0.65}


def _pick_next_speaker(
    members: list[PanelMember],
    *,
    last_speaker_id: str | None,
    difficulty: PanelDifficulty,
    allow_interruptions: bool,
    rng: random.Random,
) -> tuple[str, PanelEventType]:
    prof = _difficulty_profile(difficulty)
    if allow_interruptions and last_speaker_id and rng.random() < prof["interrupt_p"]:
        # "Interrupt" by choosing someone else (not last speaker).
        choices = [m.id for m in members if m.id != last_speaker_id] or [last_speaker_id]
        return rng.choice(choices), PanelEventType.interruption

    choices = [m.id for m in members if m.id != last_speaker_id] or [m.id for m in members]
    return rng.choice(choices), PanelEventType.question


def _followup_candidates(reactions: list[PanelReaction]) -> list[str]:
    """Return member_ids ordered by likelihood to ask a follow-up."""
    priority = {
        PanelReactionType.skeptical: 0,
        PanelReactionType.confused: 1,
        PanelReactionType.concerned: 2,
        PanelReactionType.neutral: 3,
        PanelReactionType.interested: 4,
        PanelReactionType.nodding: 5,
        PanelReactionType.impressed: 6,
    }
    scored: list[tuple[int, str]] = []
    for r in reactions:
        mid = (r.member_id or "").strip()
        if not mid:
            continue
        scored.append((priority.get(r.reaction, 3), mid))
    scored.sort(key=lambda t: t[0])
    # De-dupe while preserving order
    out: list[str] = []
    seen: set[str] = set()
    for _, mid in scored:
        if mid in seen:
            continue
        seen.add(mid)
        out.append(mid)
    return out


def _reaction_for_answer(
    answer: str, persona: InterviewerPersona, difficulty: PanelDifficulty
) -> PanelReaction:
    # Heuristic reactions to avoid hard dependency on an LLM.
    text = _compact(answer).lower()
    if not text:
        return PanelReaction(
            member_id="", reaction=PanelReactionType.confused, note="No answer provided."
        )

    long = len(text) > 900
    short = len(text) < 120
    has_numbers = any(ch.isdigit() for ch in text)
    has_structure = any(
        k in text for k in ("first", "second", "tradeoff", "because", "therefore", "however")
    )

    reaction = PanelReactionType.neutral
    note = None

    if persona.role == "Technical Lead":
        if has_numbers and has_structure:
            reaction = PanelReactionType.impressed
            note = "Clear tradeoffs and concrete details."
        elif short:
            reaction = (
                PanelReactionType.skeptical
                if difficulty != PanelDifficulty.easy
                else PanelReactionType.confused
            )
            note = "Wants more depth and specifics."
        elif long and not has_structure:
            reaction = PanelReactionType.confused
            note = "Feels rambly; wants structure."
    elif persona.role == "Hiring Manager":
        if "impact" in text or "stakeholder" in text or "align" in text:
            reaction = PanelReactionType.interested
            note = "Good ownership and alignment."
        elif short:
            reaction = PanelReactionType.skeptical
            note = "Looking for clearer outcomes."
    elif persona.role == "HR":
        if any(k in text for k in ("conflict", "feedback", "values", "motivation")):
            reaction = PanelReactionType.nodding
            note = "Strong communication signals."
        elif short:
            reaction = PanelReactionType.confused
            note = "Needs more context."
    else:
        if has_structure:
            reaction = PanelReactionType.nodding
        elif short:
            reaction = PanelReactionType.confused

    return PanelReaction(member_id="", reaction=reaction, note=note)


def _fallback_question(
    persona: InterviewerPersona, *, company: str | None, role: str | None
) -> str:
    role_txt = role.strip() if role else "this role"
    company_txt = company.strip() if company else "the company"

    if persona.role == "Technical Lead":
        return f"Walk me through a recent system you designed. What were the key tradeoffs, and how would you scale it for {company_txt}?"
    if persona.role == "Hiring Manager":
        return f"Tell me about a time you led a project with ambiguity. How did you align stakeholders and deliver outcomes for {role_txt}?"
    if persona.role == "HR":
        return "What motivates you, and what kind of environment helps you do your best work?"
    if persona.role == "Peer Engineer":
        return "Describe a tricky bug you fixed recently. How did you debug it and prevent regressions?"
    return "How do you prioritize when multiple stakeholders want different things?"


@dataclass
class PanelInterviewSimulator:
    """Orchestrates panel interview dynamics and generates events."""

    rng: random.Random = random.Random()

    def initialize_panel(self, config: PanelConfig) -> list[PanelMember]:
        personas = config.personas or _default_personas(
            config.difficulty, panel_size=config.panel_size
        )
        members: list[PanelMember] = []
        for p in personas[: config.panel_size]:
            member_id = f"p_{uuid.uuid4().hex[:10]}"
            members.append(PanelMember(id=member_id, persona=p))
        return members

    def next_question(
        self,
        *,
        config: PanelConfig,
        members: list[PanelMember],
        last_speaker_id: str | None,
        question_bank: list[str],
    ) -> tuple[str, PanelEventType, str]:
        speaker_id, event_type = _pick_next_speaker(
            members,
            last_speaker_id=last_speaker_id,
            difficulty=config.difficulty,
            allow_interruptions=config.allow_interruptions,
            rng=self.rng,
        )
        persona = next((m.persona for m in members if m.id == speaker_id), members[0].persona)
        if question_bank:
            q = self.rng.choice(question_bank)
            return speaker_id, event_type, q
        return (
            speaker_id,
            event_type,
            _fallback_question(persona, company=config.company, role=config.role),
        )

    def reactions(
        self, answer: str, members: list[PanelMember], difficulty: PanelDifficulty
    ) -> list[PanelReaction]:
        out: list[PanelReaction] = []
        for m in members:
            r = _reaction_for_answer(answer, m.persona, difficulty)
            r.member_id = m.id
            out.append(r)
        return out

    def post_answer_questions(
        self,
        *,
        config: PanelConfig,
        members: list[PanelMember],
        last_speaker_id: str | None,
        question_bank: list[str],
        reactions: list[PanelReaction],
    ) -> list[tuple[str, PanelEventType, str]]:
        """Generate 1-2 next prompts after an answer (follow-up + next question)."""
        prof = _difficulty_profile(config.difficulty)
        out: list[tuple[str, PanelEventType, str]] = []

        # Follow-up from someone who looked skeptical/confused.
        candidates = _followup_candidates(reactions)
        if candidates and self.rng.random() < prof["followup_p"]:
            follow_id = candidates[0]
            persona = next((m.persona for m in members if m.id == follow_id), members[0].persona)
            if question_bank:
                q = self.rng.choice(question_bank)
            else:
                q = _fallback_question(persona, company=config.company, role=config.role)
            out.append((follow_id, PanelEventType.follow_up, q))
            last_speaker_id = follow_id

        # Always include the next primary question (may be an interruption).
        speaker_id, ev_type, q2 = self.next_question(
            config=config,
            members=members,
            last_speaker_id=last_speaker_id,
            question_bank=question_bank,
        )
        out.append((speaker_id, ev_type, q2))
        return out


@dataclass
class PanelInterviewService:
    """High-level service: persistence + simulator + optional LLM enhancements."""

    database: Database | None = None
    collection_name: str = settings.panel_interview_sessions_collection
    simulator: PanelInterviewSimulator | None = None
    llm_service: Any | None = None
    company_interviews_service: Any | None = None

    def __post_init__(self) -> None:
        if self.database is None:
            from alfred.connectors.mongo_connector import MongoConnector

            self.database = MongoConnector().database
        self._collection: Collection = self.database.get_collection(self.collection_name)

        if self.simulator is None:
            self.simulator = PanelInterviewSimulator()

        if self.llm_service is None:
            from alfred.services.llm_service import LLMService

            self.llm_service = LLMService()

        if self.company_interviews_service is None:
            from alfred.services.company_interviews import CompanyInterviewsService

            self.company_interviews_service = CompanyInterviewsService(database=self.database)

    def ensure_indexes(self) -> None:
        try:
            self._collection.create_index([("status", 1)], name="status")
            self._collection.create_index([("created_at_dt", -1)], name="created_at_desc")
        except Exception:
            pass

    def create_session(self, payload: PanelSessionCreate) -> PanelSession:
        config = payload.config
        members = self.simulator.initialize_panel(config)
        now = _utcnow()
        total_s = int(config.total_minutes) * 60

        # Seed question bank from stored interview experiences if possible.
        bank = self._build_company_question_bank(config)

        obj_id = ObjectId()
        session = PanelSession(
            id=str(obj_id),
            config=config,
            members=members,
            status="active",
            created_at=_iso(now),
            updated_at=_iso(now),
            turn_index=0,
            time_remaining_s=total_s,
            current_speaker_id=None,
            transcript=[],
        )
        doc = session.model_dump(mode="json")
        # Persist with Mongo-native ObjectId for efficient storage + querying.
        doc["_id"] = obj_id
        doc.pop("id", None)
        doc["created_at_dt"] = now
        doc["updated_at_dt"] = now
        doc["candidate_context"] = payload.candidate_context or ""
        doc["question_bank"] = bank
        self._collection.insert_one(doc)

        # Immediately ask the first question.
        session = self._load_session(session.id)
        first_events = self._emit_next_question(session)
        return first_events.session

    def get_session(self, session_id: str) -> PanelSession:
        return self._load_session(session_id)

    def pause(self, session_id: str) -> PanelSession:
        sess = self._load_session(session_id)
        if sess.status == "completed":
            return sess
        now = _utcnow()
        self._collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"status": "paused", "updated_at": _iso(now), "updated_at_dt": now}},
        )
        return self._load_session(session_id)

    def resume(self, session_id: str) -> PanelSession:
        sess = self._load_session(session_id)
        if sess.status == "completed":
            return sess
        now = _utcnow()
        self._collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"status": "active", "updated_at": _iso(now), "updated_at_dt": now}},
        )
        return self._load_session(session_id)

    def submit_turn(self, session_id: str, payload: PanelTurnRequest) -> PanelTurnResponse:
        session = self._load_session(session_id)
        if session.status != "active":
            raise ServiceUnavailableError(f"Session is not active (status={session.status})")

        now = _utcnow()
        answer_event = PanelEvent(
            type=PanelEventType.answer,
            timestamp=_iso(now),
            member_id=None,
            text=payload.answer,
        )

        reactions = self.simulator.reactions(
            payload.answer, session.members, session.config.difficulty
        )
        reaction_event = PanelEvent(
            type=PanelEventType.reaction,
            timestamp=_iso(now),
            reactions=reactions,
            meta={"time_pressure": bool(session.config.time_pressure)},
        )

        # Persist answer + reactions.
        add_events = [answer_event.model_dump(mode="json"), reaction_event.model_dump(mode="json")]
        self._collection.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$push": {"transcript": {"$each": add_events}},
                "$set": {
                    "turn_index": int(session.turn_index) + 1,
                    "updated_at": _iso(now),
                    "updated_at_dt": now,
                },
            },
        )

        # Decrement time remaining (coarse heuristic).
        elapsed = 60 if session.config.time_pressure else 30
        self._collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$inc": {"time_remaining_s": -int(elapsed)}},
        )

        updated = self._load_session(session_id)
        # Emit follow-up and/or next question (may be 2 events).
        question_events = self._emit_post_answer_prompts(updated, reactions=reactions)
        question_events.events.insert(0, reaction_event)
        question_events.events.insert(0, answer_event)
        return question_events

    def feedback(self, session_id: str) -> PanelFeedback:
        session = self._load_session(session_id)
        # LLM-backed per-persona feedback when OpenAI is configured; otherwise deterministic fallback.
        try:
            return self._llm_feedback(session)
        except Exception as exc:
            logger.info("Panel feedback fallback: %s", exc)
            return self._fallback_feedback(session)

    # ---------------- internal helpers ----------------

    def _load_session(self, session_id: str) -> PanelSession:
        if not ObjectId.is_valid(session_id):
            raise ValueError("Invalid session_id")
        doc = self._collection.find_one({"_id": ObjectId(session_id)})
        if not doc:
            raise ValueError("Session not found")
        # Normalize id field
        doc["id"] = str(doc.pop("_id"))
        doc.pop("candidate_context", None)
        doc.pop("question_bank", None)
        doc.pop("created_at_dt", None)
        doc.pop("updated_at_dt", None)
        return PanelSession.model_validate(doc)

    def _get_question_bank(self, session_id: str) -> list[str]:
        if not ObjectId.is_valid(session_id):
            return []
        doc = self._collection.find_one({"_id": ObjectId(session_id)}, {"question_bank": 1})
        bank = (doc or {}).get("question_bank")
        if isinstance(bank, list):
            return [q for q in bank if isinstance(q, str) and q.strip()]
        return []

    def _emit_next_question(self, session: PanelSession) -> PanelTurnResponse:
        now = _utcnow()
        events = self._try_llm_prompts(session, reactions=None, max_prompts=1)
        if not events:
            bank = self._get_question_bank(session.id)
            speaker_id, ev_type, question = self.simulator.next_question(
                config=session.config,
                members=session.members,
                last_speaker_id=session.current_speaker_id,
                question_bank=bank,
            )
            events = [
                PanelEvent(
                    type=ev_type,
                    timestamp=_iso(now),
                    member_id=speaker_id,
                    text=question,
                    meta={"time_remaining_s": int(session.time_remaining_s)},
                )
            ]

        self._collection.update_one(
            {"_id": ObjectId(session.id)},
            {
                "$push": {"transcript": {"$each": [e.model_dump(mode="json") for e in events]}},
                "$set": {
                    "current_speaker_id": events[-1].member_id,
                    "updated_at": _iso(now),
                    "updated_at_dt": now,
                },
            },
        )
        updated = self._load_session(session.id)
        return PanelTurnResponse(session=updated, events=events)

    def _emit_post_answer_prompts(
        self,
        session: PanelSession,
        *,
        reactions: list[PanelReaction],
    ) -> PanelTurnResponse:
        now = _utcnow()
        events = self._try_llm_prompts(session, reactions=reactions, max_prompts=2)
        if not events:
            bank = self._get_question_bank(session.id)
            prompts = self.simulator.post_answer_questions(
                config=session.config,
                members=session.members,
                last_speaker_id=session.current_speaker_id,
                question_bank=bank,
                reactions=reactions,
            )
            events = []
            for speaker_id, ev_type, question in prompts[:2]:
                events.append(
                    PanelEvent(
                        type=ev_type,
                        timestamp=_iso(now),
                        member_id=speaker_id,
                        text=question,
                        meta={"time_remaining_s": int(session.time_remaining_s)},
                    )
                )

        self._collection.update_one(
            {"_id": ObjectId(session.id)},
            {
                "$push": {"transcript": {"$each": [e.model_dump(mode="json") for e in events]}},
                "$set": {
                    "current_speaker_id": events[-1].member_id
                    if events
                    else session.current_speaker_id,
                    "updated_at": _iso(now),
                    "updated_at_dt": now,
                },
            },
        )

        updated = self._load_session(session.id)

        # Emit a time-pressure note when near the end.
        if updated.config.time_pressure and int(updated.time_remaining_s) <= 5 * 60:
            note = PanelEvent(
                type=PanelEventType.note,
                timestamp=_iso(now),
                text="You’re running low on time — keep answers structured and concise.",
                meta={"time_remaining_s": int(updated.time_remaining_s)},
            )
            self._collection.update_one(
                {"_id": ObjectId(session.id)},
                {"$push": {"transcript": note.model_dump(mode="json")}},
            )
            updated = self._load_session(session.id)
            events.append(note)

        return PanelTurnResponse(session=updated, events=events)

    def _try_llm_prompts(
        self,
        session: PanelSession,
        *,
        reactions: list[PanelReaction] | None,
        max_prompts: int,
    ) -> list[PanelEvent]:
        # Only use structured prompts when OpenAI is configured; otherwise fall back to heuristics.
        if not (settings.openai_api_key and settings.openai_api_key.get_secret_value()):
            return []

        from pydantic import BaseModel, Field

        allowed_ids = [m.id for m in session.members]

        class _Prompt(BaseModel):
            member_id: str = Field(..., description="Must be one of the provided panel member ids.")
            type: str = Field(..., description="question | follow_up | interruption")
            text: str

        class _Out(BaseModel):
            prompts: list[_Prompt] = Field(default_factory=list)

        # Compact transcript context (last few events).
        transcript = []
        for e in session.transcript[-10:]:
            who = e.member_id or "candidate"
            transcript.append(
                f"{e.type.value}({who}): {(_compact(e.text)[:240] if e.text else '')}"
            )

        bank = self._get_question_bank(session.id)
        bank_snips = "\n".join(f"- {q}" for q in bank[:12]) if bank else "- (none)"

        reaction_snips = []
        if reactions:
            for r in reactions:
                reaction_snips.append(f"- {r.member_id}: {r.reaction.value} ({r.note or ''})")
        reaction_text = "\n".join(reaction_snips) if reaction_snips else "- (none)"

        member_desc = "\n".join(
            f"- {m.id}: {m.persona.role}, personality={m.persona.personality}, style={m.persona.questioning_style}, focus={m.persona.focus_areas}"
            for m in session.members
        )

        user = (
            "You are simulating a realistic panel interview.\n"
            f"Difficulty: {session.config.difficulty.value}\n"
            f"Company: {session.config.company or ''}\n"
            f"Role: {session.config.role or ''}\n"
            f"Time remaining (seconds): {int(session.time_remaining_s)}\n"
            f"Allow interruptions: {bool(session.config.allow_interruptions)}\n"
            f"Max prompts to output: {int(max_prompts)}\n\n"
            "Panel members (use these ids exactly):\n"
            + member_desc
            + "\n\nRecent transcript:\n"
            + ("\n".join(transcript) if transcript else "- (empty)")
            + "\n\nPanel reactions to the last answer:\n"
            + reaction_text
            + "\n\nCompany question bank (optional; prefer these when relevant):\n"
            + bank_snips
            + "\n\nRules:\n"
            "- Output 1 to Max prompts.\n"
            "- Each prompt should sound like the persona.\n"
            "- Prompts must be concise and specific.\n"
            "- Use type=follow_up when reacting to the last answer.\n"
            "- type=interruption only if it feels natural.\n"
            "- member_id must be one of the provided ids.\n"
        )

        out: _Out = self.llm_service.structured(
            [
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": user},
            ],
            schema=_Out,
        )

        events: list[PanelEvent] = []
        now = _utcnow()
        for p in out.prompts[:max_prompts]:
            if p.member_id not in allowed_ids:
                continue
            t = (p.type or "").strip().lower()
            if t == "follow_up":
                ev_type = PanelEventType.follow_up
            elif t == "interruption":
                ev_type = PanelEventType.interruption
            else:
                ev_type = PanelEventType.question
            events.append(
                PanelEvent(
                    type=ev_type,
                    timestamp=_iso(now),
                    member_id=p.member_id,
                    text=p.text.strip(),
                    meta={"time_remaining_s": int(session.time_remaining_s), "llm": True},
                )
            )
        return events

    def _build_company_question_bank(self, config: PanelConfig) -> list[str]:
        if not (config.include_company_question_bank and config.company):
            return []
        company = config.company.strip()
        if not company:
            return []

        try:
            rows = self.company_interviews_service.list_interviews(
                company=company,
                provider=None,
                role=None,
                limit=max(1, min(int(config.max_company_questions), 200)),
                skip=0,
            )
        except Exception:
            return []

        questions: list[str] = []
        for r in rows:
            qs = r.get("questions")
            if isinstance(qs, list):
                for q in qs:
                    if isinstance(q, str) and q.strip():
                        questions.append(q.strip())
        # De-dupe while preserving order
        seen: set[str] = set()
        out: list[str] = []
        for q in questions:
            if q in seen:
                continue
            seen.add(q)
            out.append(q)
        return out[: int(config.max_company_questions)]

    def _fallback_feedback(self, session: PanelSession) -> PanelFeedback:
        by_member: list[PanelFeedbackItem] = []
        for m in session.members:
            by_member.append(
                PanelFeedbackItem(
                    member_id=m.id,
                    strengths=["Clear communication when structured."],
                    improvements=["Add more concrete examples and quantify impact."],
                    score=7,
                    summary=f"{m.persona.role} feedback (fallback).",
                )
            )
        return PanelFeedback(
            session_id=session.id,
            overall_summary="Solid performance. Improve specificity and structure under time pressure.",
            overall_score=7,
            by_member=by_member,
        )

    def _llm_feedback(self, session: PanelSession) -> PanelFeedback:
        # If OpenAI isn't configured, LLMService.structured will fail; bubble up to fallback.
        from pydantic import BaseModel, Field

        class _Out(BaseModel):
            overall_summary: str
            overall_score: int | None = Field(default=None, ge=1, le=10)
            by_member: list[PanelFeedbackItem] = Field(default_factory=list)

        transcript = []
        for e in session.transcript[-60:]:
            who = e.member_id or "candidate"
            transcript.append(
                f"{e.type.value} ({who}): {(_compact(e.text)[:400] if e.text else '')}"
            )
        members = [
            f"- {m.id}: {m.persona.role} ({m.persona.personality}), focus={m.persona.focus_areas}"
            for m in session.members
        ]
        user = (
            "You are an interview panel giving actionable feedback.\n"
            "Return feedback matching the schema.\n\n"
            "Panel members:\n" + "\n".join(members) + "\n\nTranscript:\n" + "\n".join(transcript)
        )

        out: _Out = self.llm_service.structured(
            [
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": user},
            ],
            schema=_Out,
        )
        return PanelFeedback(
            session_id=session.id,
            overall_summary=out.overall_summary,
            overall_score=out.overall_score,
            by_member=out.by_member,
        )
