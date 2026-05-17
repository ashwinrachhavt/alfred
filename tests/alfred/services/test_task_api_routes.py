from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from alfred.api.dependencies import get_current_user, get_db_session
from alfred.api.tasks import router
from alfred.core.auth import AuthUser


def _client() -> TestClient:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    app = FastAPI()
    app.include_router(router)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = session_override

    async def current_user_override():
        return AuthUser(user_id="user_1")

    app.dependency_overrides[get_current_user] = current_user_override
    return TestClient(app)


def test_task_api_crud_and_done() -> None:
    client = _client()

    created = client.post("/api/task-system/tasks", json={"title": "API task"})
    assert created.status_code == 201, created.text
    task = created.json()

    listed = client.get("/api/task-system/tasks")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    got = client.get(f"/api/task-system/tasks/{task['id']}")
    assert got.status_code == 200
    assert got.json()["title"] == "API task"

    patched = client.patch(f"/api/task-system/tasks/{task['id']}", json={"title": "API task updated"})
    assert patched.status_code == 200
    assert patched.json()["title"] == "API task updated"

    done = client.patch(f"/api/task-system/tasks/{task['id']}/done", json={"award_rewards": False})
    assert done.status_code == 200
    assert done.json()["task"]["status"] == "DONE"

    deleted = client.delete(f"/api/task-system/tasks/{task['id']}")
    assert deleted.status_code == 204
