from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from alfred.services.agent.tools import execute_tool
from alfred.services.notes_service import NotesService


def _session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


@pytest.mark.asyncio
async def test_agent_tool_imports_server_visible_folder_into_default_notes_workspace() -> None:
    session = _session()

    with TemporaryDirectory() as temp_dir:
        source_root = Path(temp_dir) / "notes-export"
        source_root.mkdir()
        (source_root / "settings.json").write_text('{"theme":"dark"}\n', encoding="utf-8")

        result = await execute_tool(
            "import_notes_from_filesystem",
            {"path": str(source_root), "max_files": 20},
            session,
        )

    assert result["action"] == "imported_notes"
    assert result["workspace_name"] == "Personal"
    assert result["imported_count"] == 2
    assert result["skipped_count"] == 0

    notes = NotesService(session)
    workspace = notes.list_workspaces()[0]
    rows = notes.tree(workspace_id=workspace.id)
    titles = {row.title for row in rows}

    assert "notes-export" in titles
    assert "settings.json" in titles
