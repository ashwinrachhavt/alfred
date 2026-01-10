from __future__ import annotations

from alfred.api.notes import routes as notes_routes
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel


def _client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _get_db_session():
        with Session(engine) as session:
            yield session

    app = FastAPI()
    app.include_router(notes_routes.router)
    app.dependency_overrides[notes_routes.get_db_session] = _get_db_session
    return TestClient(app)


def test_create_note_creates_default_workspace():
    client = _client()
    resp = client.post("/api/v1/notes", params={"user_id": 1}, json={"title": "Hello"})
    assert resp.status_code == 201
    note = resp.json()
    assert note["title"] == "Hello"
    assert note["workspace_id"]

    workspaces = client.get("/api/v1/workspaces", params={"user_id": 1})
    assert workspaces.status_code == 200
    items = workspaces.json()
    assert len(items) == 1
    assert items[0]["id"] == note["workspace_id"]


def test_tree_and_move_reorders_root_notes():
    client = _client()

    a = client.post("/api/v1/notes", params={"user_id": 1}, json={"title": "A"}).json()
    client.post("/api/v1/notes", params={"user_id": 1}, json={"title": "B"}).json()
    c = client.post("/api/v1/notes", params={"user_id": 1}, json={"title": "C"}).json()

    workspace_id = a["workspace_id"]

    resp = client.get("/api/v1/notes/tree", params={"workspace_id": workspace_id})
    assert resp.status_code == 200
    root_titles = [n["note"]["title"] for n in resp.json()["items"]]
    assert root_titles == ["A", "B", "C"]

    moved = client.post(
        f"/api/v1/notes/{c['id']}/move",
        params={"user_id": 1},
        json={"parent_id": None, "position": 1},
    )
    assert moved.status_code == 200

    resp = client.get("/api/v1/notes/tree", params={"workspace_id": workspace_id})
    assert resp.status_code == 200
    root_titles = [n["note"]["title"] for n in resp.json()["items"]]
    assert root_titles == ["A", "C", "B"]


def test_prevent_cycle_move():
    client = _client()
    parent = client.post("/api/v1/notes", params={"user_id": 1}, json={"title": "Parent"}).json()
    child = client.post(
        "/api/v1/notes",
        params={"user_id": 1},
        json={
            "title": "Child",
            "workspace_id": parent["workspace_id"],
            "parent_id": parent["id"],
        },
    ).json()

    resp = client.post(
        f"/api/v1/notes/{parent['id']}/move",
        params={"user_id": 1},
        json={"parent_id": child["id"], "position": 0},
    )
    assert resp.status_code == 409


def test_delete_archives_note():
    client = _client()
    note = client.post("/api/v1/notes", params={"user_id": 1}, json={"title": "Temp"}).json()

    deleted = client.delete(f"/api/v1/notes/{note['id']}", params={"user_id": 1})
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    get_again = client.get(f"/api/v1/notes/{note['id']}")
    assert get_again.status_code == 404

    tree = client.get("/api/v1/notes/tree", params={"workspace_id": note["workspace_id"]})
    assert tree.status_code == 200
    assert tree.json()["items"] == []
