from __future__ import annotations

from alfred.api.interviews.routes import router
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakeInterviewPrepService:
    def __init__(self) -> None:
        self.record = {
            "id": "507f1f77bcf86cd799439011",
            "company": "ExampleCo",
            "role": "Backend Engineer",
            "quiz": {
                "questions": [
                    {
                        "question": "What is CAP theorem?",
                        "answer": "Consistency availability partition tolerance",
                    },
                    {"question": "Define idempotency.", "answer": "same result when repeated"},
                ],
                "score": None,
                "attempts": [],
            },
        }

    def get(self, _id: str):  # noqa: ANN001
        return dict(self.record)

    def update(self, _id: str, patch):  # noqa: ANN001
        if patch.quiz is not None:
            self.record["quiz"] = patch.quiz.model_dump()
        return True


def _create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    from alfred.api.interviews import routes as interview_routes

    svc = _FakeInterviewPrepService()
    app.dependency_overrides[interview_routes.get_interview_prep_service] = lambda: svc
    return app


def test_quiz_attempt_scoring_exact_match_normalized():
    client = TestClient(_create_app())
    resp = client.post(
        "/api/interviews/507f1f77bcf86cd799439011/quiz/attempt",
        json={
            "answers": {
                "0": "Consistency, Availability, Partition Tolerance",
                "1": "Same result when repeated.",
            }
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["gradable"] == 2
    assert data["correct"] == 2
    assert data["score"] == 1.0
