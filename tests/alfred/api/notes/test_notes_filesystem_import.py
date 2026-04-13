from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from alfred.api.notes import routes as notes_routes


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


def _flatten_tree(nodes: list[dict]) -> list[dict]:
    items: list[dict] = []
    for node in nodes:
        items.append(node)
        items.extend(_flatten_tree(node.get("children", [])))
    return items


def test_browse_filesystem_lists_hidden_entries() -> None:
    client = _client()

    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / ".claude").mkdir()
        (root / ".gstack").mkdir()
        (root / "README.md").write_text("# Alfred\n", encoding="utf-8")

        response = client.get("/api/v1/notes/filesystem/browse", params={"path": str(root)})

    assert response.status_code == 200
    data = response.json()
    by_name = {item["name"]: item for item in data["items"]}
    assert by_name[".claude"]["kind"] == "directory"
    assert by_name[".claude"]["hidden"] is True
    assert by_name["README.md"]["importable"] is True


def test_import_filesystem_directory_creates_note_tree() -> None:
    client = _client()
    workspace = client.post("/api/v1/workspaces", json={"name": "Imports", "icon": "📓"}).json()

    with TemporaryDirectory() as temp_dir:
        source_root = Path(temp_dir) / ".claude"
        agents_dir = source_root / "agents"
        agents_dir.mkdir(parents=True)
        (source_root / "settings.json").write_text('{"theme":"dark"}\n', encoding="utf-8")
        (agents_dir / "system.md").write_text("# System prompt\n", encoding="utf-8")
        (source_root / "binary.bin").write_bytes(b"\x00\x01\x02")

        imported = client.post(
            "/api/v1/notes/filesystem/import",
            json={"workspace_id": workspace["id"], "path": str(source_root)},
        )

    assert imported.status_code == 201
    result = imported.json()
    assert result["imported_count"] == 4
    assert result["skipped_count"] == 1
    assert result["source_path"].endswith(".claude")

    tree = client.get("/api/v1/notes/tree", params={"workspace_id": workspace["id"]})
    assert tree.status_code == 200

    items = tree.json()["items"]
    assert len(items) == 1
    assert items[0]["note"]["title"] == ".claude"
    assert items[0]["note"]["icon"] == "📁"

    flattened = _flatten_tree(items)
    titles = [node["note"]["title"] for node in flattened]
    assert ".claude" in titles
    assert "agents" in titles
    assert "settings.json" in titles
    assert "system.md" in titles

    settings_node = next(node for node in flattened if node["note"]["title"] == "settings.json")
    settings_note = client.get(f"/api/v1/notes/{settings_node['note']['id']}")
    assert settings_note.status_code == 200
    assert settings_note.json()["content_markdown"] == '{"theme":"dark"}\n'
