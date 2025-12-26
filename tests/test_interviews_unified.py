from __future__ import annotations

from typing import Any

from alfred.api.interviews_unified import router as interviews_unified_router
from alfred.core.dependencies import get_unified_interview_agent
from alfred.core.exceptions import register_exception_handlers
from alfred.schemas.interview_questions import (
    InterviewQuestionsReport,
    QuestionItem,
    QuestionSource,
)
from alfred.schemas.panel_interview import (
    InterviewerPersona,
    PanelConfig,
    PanelEvent,
    PanelEventType,
    PanelMember,
    PanelReaction,
    PanelReactionType,
    PanelSession,
    PanelSessionCreate,
    PanelTurnRequest,
    PanelTurnResponse,
)
from alfred.services.interview_service import UnifiedInterviewAgent
from fastapi import FastAPI
from fastapi.testclient import TestClient


class StubInterviewQuestionsService:
    def generate_report(
        self,
        company: str,
        *,
        role: str | None = None,
        max_sources: int = 12,
        max_questions: int = 60,
        use_firecrawl_search: bool = True,
    ) -> InterviewQuestionsReport:
        _ = (max_sources, max_questions, use_firecrawl_search)
        questions = [
            QuestionItem(
                question="Explain the difference between a process and a thread.",
                categories=["coding"],
                occurrences=2,
                sources=["https://example.com/q1"],
            )
        ]
        sources = [
            QuestionSource(
                url="https://example.com/q1",
                title="Example",
                snippet="Example snippet",
                provider="stub",
                questions=[questions[0].question],
            )
        ]
        return InterviewQuestionsReport(
            company=company,
            role=role,
            queries=[f"{company} interview questions"],
            total_unique_questions=len(questions),
            questions=questions,
            sources=sources,
            warnings=[],
            meta={"stub": True},
        )


class StubCompanyResearchService:
    def generate_report(self, company: str, *, refresh: bool = False) -> dict[str, Any]:
        _ = refresh
        return {
            "company": company,
            "report": {
                "executive_summary": f"{company} builds example products.",
                "sections": [
                    {
                        "name": "Market",
                        "summary": "A competitive space with rapid iteration cycles.",
                        "insights": ["Differentiation comes from execution speed. [stub]"],
                    }
                ],
            },
        }


class StubPanelInterviewService:
    def __init__(self) -> None:
        self._next_id = 1

    def create_session(self, payload: PanelSessionCreate) -> PanelSession:
        session_id = f"stub-session-{self._next_id}"
        self._next_id += 1
        now = "2025-01-01T00:00:00Z"

        personas = payload.config.personas or [
            InterviewerPersona(
                name="Alex",
                role="Technical Lead",
                personality="detail-oriented",
                focus_areas=["coding"],
                questioning_style="direct",
            )
        ]
        members = [PanelMember(id=str(i + 1), persona=p) for i, p in enumerate(personas)]
        return PanelSession(
            id=session_id,
            config=payload.config,
            members=members,
            status="active",
            created_at=now,
            updated_at=now,
            turn_index=0,
            time_remaining_s=60,
            current_speaker_id=None,
            transcript=[],
        )

    def submit_turn(self, session_id: str, payload: PanelTurnRequest) -> PanelTurnResponse:
        _ = payload
        now = "2025-01-01T00:00:00Z"
        session = PanelSession(
            id=session_id,
            config=PanelConfig(company="Acme", role="Software Engineer"),
            members=[],
            status="active",
            created_at=now,
            updated_at=now,
            turn_index=1,
            time_remaining_s=60,
            current_speaker_id=None,
            transcript=[],
        )
        events = [
            PanelEvent(type=PanelEventType.answer, timestamp=now, text="(candidate answer)"),
            PanelEvent(
                type=PanelEventType.question,
                timestamp=now,
                member_id="1",
                text="Tell me about a time you handled a difficult bug end-to-end.",
                reactions=[PanelReaction(member_id="1", reaction=PanelReactionType.neutral)],
            ),
        ]
        return PanelTurnResponse(session=session, events=events)


def _make_client(agent: UnifiedInterviewAgent) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(interviews_unified_router)
    app.dependency_overrides[get_unified_interview_agent] = lambda: agent
    return TestClient(app)


def _make_agent() -> UnifiedInterviewAgent:
    return UnifiedInterviewAgent(
        questions_service=StubInterviewQuestionsService(),  # type: ignore[arg-type]
        company_research_service=StubCompanyResearchService(),  # type: ignore[arg-type]
        panel_service=StubPanelInterviewService(),  # type: ignore[arg-type]
    )


def test_unified_deep_research_compiles_report() -> None:
    client = _make_client(_make_agent())
    res = client.post(
        "/api/interviews-unified/process",
        json={
            "operation": "deep_research",
            "company": "Acme",
            "role": "Software Engineer",
            "target_length_words": 500,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["operation"] == "deep_research"
    assert "Interview Preparation Report" in (data["research_report"] or "")
    assert data["key_insights"] and "execution speed" in data["key_insights"][0].lower()


def test_unified_practice_session_returns_session_id() -> None:
    client = _make_client(_make_agent())
    res = client.post(
        "/api/interviews-unified/process",
        json={"operation": "practice_session", "company": "Acme", "role": "Software Engineer"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["operation"] == "practice_session"
    assert data["session_id"]


def test_unified_practice_session_returns_next_question_after_answer() -> None:
    agent = _make_agent()
    client = _make_client(agent)

    first = client.post(
        "/api/interviews-unified/process",
        json={"operation": "practice_session", "company": "Acme", "role": "Software Engineer"},
    )
    session_id = first.json()["session_id"]

    res = client.post(
        "/api/interviews-unified/process",
        json={
            "operation": "practice_session",
            "company": "Acme",
            "role": "Software Engineer",
            "session_id": session_id,
            "candidate_response": "I would start by...",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == session_id
    assert "bug" in (data["interviewer_response"] or "").lower()
