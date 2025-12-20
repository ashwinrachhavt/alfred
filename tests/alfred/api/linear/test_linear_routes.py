from alfred.api.linear import router as linear_router
from alfred.services.linear import get_linear_service
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakeLinearService:
    def list_issues(self, *, include_comments: bool, limit: int):
        assert include_comments is False
        assert limit == 2
        return [{"id": "1", "identifier": "ENG-1", "title": "One"}]

    def list_issues_by_date_range(
        self, *, start_date: str, end_date: str, include_comments: bool, limit: int
    ):
        raise AssertionError("not called")

    def format_issue(self, issue):
        return {"id": issue["id"], "title": issue["title"]}

    def issue_to_markdown(self, issue):
        return f"# {issue['identifier']}: {issue['title']}"


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(linear_router)
    return app


def test_linear_status_unconfigured_does_not_error():
    client = TestClient(create_app())
    resp = client.get("/api/linear/status")
    assert resp.status_code == 200
    assert resp.json() == {"configured": False}


def test_linear_list_issues_uses_dependency_override():
    app = create_app()
    app.dependency_overrides[get_linear_service] = lambda: _FakeLinearService()
    client = TestClient(app)

    resp = client.get("/api/linear/issues?limit=2")
    assert resp.status_code == 200
    assert resp.json() == {
        "count": 1,
        "items": [{"id": "1", "identifier": "ENG-1", "title": "One"}],
    }
