from __future__ import annotations

from alfred.api.interviews.routes import get_prep_doc_generator, get_quiz_generator, router
from alfred.schemas.interview_prep import InterviewQuiz, PrepDoc
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakeInterviewPrepService:
    def __init__(self) -> None:
        self._data = {
            "id": "507f1f77bcf86cd799439011",
            "company": "ExampleCo",
            "role": "Backend Engineer",
            "prep_doc": {},
            "quiz": {},
        }

    def create(self, payload):  # noqa: ANN001
        return self._data["id"]

    def get(self, _id: str):  # noqa: ANN001
        return dict(self._data)

    def update(self, _id: str, patch):  # noqa: ANN001
        if patch.prep_doc is not None:
            self._data["prep_doc"] = patch.prep_doc.model_dump()
        if patch.quiz is not None:
            self._data["quiz"] = patch.quiz.model_dump()
        if patch.performance_rating is not None:
            self._data["performance_rating"] = patch.performance_rating
        if patch.confidence_rating is not None:
            self._data["confidence_rating"] = patch.confidence_rating
        return True


class _FakePrepGen:
    def generate_prep_doc(self, **_kwargs):  # noqa: ANN001
        return PrepDoc(
            company_overview="Company",
            role_analysis="Role",
            star_stories=[],
            likely_questions=[],
            technical_topics=[],
        )


class _FakeQuizGen:
    def generate_quiz(self, **_kwargs):  # noqa: ANN001
        return InterviewQuiz(questions=[], score=None, attempts=[])


def _create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_prep_doc_generator] = lambda: _FakePrepGen()
    app.dependency_overrides[get_quiz_generator] = lambda: _FakeQuizGen()
    # Override the cached dependency by directly overriding the function imported in routes.
    from alfred.api.interviews import routes as interview_routes

    svc = _FakeInterviewPrepService()
    app.dependency_overrides[interview_routes.get_interview_prep_service] = lambda: svc
    app.dependency_overrides[interview_routes.get_job_application_service] = lambda: type(
        "_JobApps", (), {"update": lambda *_args, **_kwargs: True}
    )()
    return app


def test_detect_creates_record():
    client = TestClient(_create_app())
    resp = client.post(
        "/api/interviews/detect", json={"company": "ExampleCo", "role": "Backend Engineer"}
    )
    assert resp.status_code == 200
    assert "interview_prep_id" in resp.json()


def test_generate_and_get_prep_doc():
    client = TestClient(_create_app())
    resp = client.post("/api/interviews/507f1f77bcf86cd799439011/prep", json={})
    assert resp.status_code == 200
    assert resp.json()["company_overview"] == "Company"

    resp2 = client.get("/api/interviews/507f1f77bcf86cd799439011/prep")
    assert resp2.status_code == 200
    assert resp2.json()["role_analysis"] == "Role"


def test_generate_quiz():
    client = TestClient(_create_app())
    resp = client.post("/api/interviews/507f1f77bcf86cd799439011/quiz", json={"num_questions": 10})
    assert resp.status_code == 200
    assert resp.json()["questions"] == []


def test_feedback():
    client = TestClient(_create_app())
    resp = client.patch(
        "/api/interviews/507f1f77bcf86cd799439011/feedback",
        json={"performance_rating": 8},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
