from __future__ import annotations

import base64

from alfred.api.interviews.routes import get_gmail_connector_maybe, router
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakeInterviewPrepService:
    def create(self, _payload):  # noqa: ANN001
        return "507f1f77bcf86cd799439011"

    def update(self, _id: str, _patch):  # noqa: ANN001
        return True


class _FakeGmailConnector:
    async def get_message_details(self, _message_id: str):  # noqa: ANN001
        body = "See you for the interview. https://meet.google.com/abc-defg-hij"
        data = base64.urlsafe_b64encode(body.encode("utf-8")).decode("ascii").rstrip("=")
        return (
            {
                "snippet": "See you for the interview.",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [
                        {
                            "name": "Subject",
                            "value": "Interview with ExampleCo for Backend Engineer",
                        }
                    ],
                    "body": {"data": data},
                },
            },
            None,
        )


def _create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    from alfred.api.interviews import routes as interview_routes

    app.dependency_overrides[interview_routes.get_interview_prep_service] = (
        lambda: _FakeInterviewPrepService()
    )
    app.dependency_overrides[interview_routes.get_job_application_service] = lambda: type(
        "_JobApps", (), {"update": lambda *_args, **_kwargs: True}
    )()
    app.dependency_overrides[get_gmail_connector_maybe] = lambda: _FakeGmailConnector()
    return app


def test_detect_from_gmail_message_id_extracts_company_and_role():
    client = TestClient(_create_app())
    resp = client.post("/api/interviews/detect", json={"gmail_message_id": "abc123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["interview_prep_id"] == "507f1f77bcf86cd799439011"
    assert data["detected"]["company"] == "ExampleCo"
    assert data["detected"]["role"] == "Backend Engineer"
