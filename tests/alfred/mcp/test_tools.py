"""Unit tests for Alfred MCP tools.

Uses SQLite in-memory DB, same pattern as test_zettelkasten_service.py.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

import alfred.models.doc_storage

# Import models to register them in SQLModel.metadata before create_all
import alfred.models.zettel  # noqa: F401
from alfred.services.zettelkasten_service import ZettelkastenService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_engine_and_session():
    """Create an in-memory SQLite engine with StaticPool.

    StaticPool ensures all sessions share the SAME connection, so:
    - Tables created by create_all are visible to all sessions
    - Data inserted by the test fixture is visible to tool sessions
    - asyncio.to_thread can access the same DB (check_same_thread=False)
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    return engine, session


@dataclass
class _FakeAlfredContext:
    session_factory: Any
    session_id: str = "test-session-id"


class _FakeRequestContext:
    def __init__(self, ctx: _FakeAlfredContext):
        self.lifespan_context = ctx


class _FakeContext:
    """Minimal stand-in for mcp.server.fastmcp.Context."""

    def __init__(self, session_factory):
        self.request_context = _FakeRequestContext(
            _FakeAlfredContext(session_factory=session_factory, session_id="test-session")
        )


def _fixture():
    """Create an in-memory session + fake MCP context.

    Uses check_same_thread=False so asyncio.to_thread can access the DB.
    The factory creates NEW sessions from the same engine so _db_session's
    close() doesn't destroy the test session, but data is visible across
    sessions (shared in-memory DB).
    """
    engine, session = _make_engine_and_session()

    def factory():
        return Session(engine)

    ctx = _FakeContext(session_factory=factory)
    svc = ZettelkastenService(session=session)
    return session, ctx, svc


# ---------------------------------------------------------------------------
# search_knowledge
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_knowledge_happy_path():
    from alfred.mcp.tools import search_knowledge

    _, ctx, svc = _fixture()
    svc.create_card(title="System Design Patterns", content="Microservices, event sourcing", topic="system design")
    svc.create_card(title="Cooking Tips", content="How to boil pasta", topic="cooking")

    results = await search_knowledge(query="system design", limit=10, ctx=ctx)
    assert len(results) == 1
    assert results[0]["title"] == "System Design Patterns"
    assert results[0]["type"] == "zettel"


@pytest.mark.asyncio
async def test_search_knowledge_topic_filter():
    from alfred.mcp.tools import search_knowledge

    _, ctx, svc = _fixture()
    svc.create_card(title="AI Card", content="neural networks", topic="ai")
    svc.create_card(title="AI in Finance", content="neural networks in trading", topic="finance")

    results = await search_knowledge(query="neural", topic="ai", ctx=ctx)
    assert len(results) == 1
    assert results[0]["topic"] == "ai"


@pytest.mark.asyncio
async def test_search_knowledge_empty_results():
    from alfred.mcp.tools import search_knowledge

    _, ctx, svc = _fixture()
    results = await search_knowledge(query="nonexistent xyz", ctx=ctx)
    assert results == []


# ---------------------------------------------------------------------------
# get_zettel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_zettel_found():
    from alfred.mcp.tools import get_zettel

    _, ctx, svc = _fixture()
    card = svc.create_card(title="Test Card", content="Some content", topic="test", tags=["a", "b"])

    result = await get_zettel(zettel_id=card.id, ctx=ctx)
    assert result["title"] == "Test Card"
    assert result["content"] == "Some content"
    assert result["topic"] == "test"
    assert "related_ids" in result


@pytest.mark.asyncio
async def test_get_zettel_not_found():
    from alfred.mcp.tools import get_zettel

    _, ctx, _ = _fixture()
    result = await get_zettel(zettel_id=99999, ctx=ctx)
    assert "error" in result


# ---------------------------------------------------------------------------
# get_document
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_document_found():
    from datetime import date

    from alfred.mcp.tools import get_document
    from alfred.models.doc_storage import DocumentRow

    session, ctx, _ = _fixture()
    doc_id = uuid4()
    doc = DocumentRow(
        id=doc_id,
        source_url="https://example.com",
        title="Test Doc",
        cleaned_text="This is the document content for testing.",
        hash="abc123unique",
        tags=[],
        day_bucket=date.today(),
    )
    session.add(doc)
    session.commit()

    result = await get_document(document_id=str(doc_id), ctx=ctx)
    assert result["title"] == "Test Doc"
    assert "cleaned_text_preview" in result


@pytest.mark.asyncio
async def test_get_document_not_found():
    from alfred.mcp.tools import get_document

    _, ctx, _ = _fixture()
    result = await get_document(document_id=str(uuid4()), ctx=ctx)
    assert "error" in result


# ---------------------------------------------------------------------------
# get_related
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_related_no_embedding():
    from alfred.mcp.tools import get_related

    _, ctx, svc = _fixture()
    card = svc.create_card(title="Card Without Embedding", content="No embedding here")

    result = await get_related(item_id=card.id, ctx=ctx)
    # find_similar_cards requires source card to have embedding — returns empty or error
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_related_card_not_found():
    from alfred.mcp.tools import get_related

    _, ctx, _ = _fixture()
    result = await get_related(item_id=99999, ctx=ctx)
    assert len(result) >= 1
    assert "error" in result[0]


# ---------------------------------------------------------------------------
# save_insight
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_insight_creates_card():
    from alfred.mcp.tools import save_insight

    _, ctx, svc = _fixture()

    with patch("alfred.services.zettelkasten_service.ZettelkastenService.ensure_embedding"):
        result = await save_insight(
            title="New Insight",
            content="Something I learned",
            topic="learning",
            tags=["test"],
            ctx=ctx,
        )

    assert result["title"] == "New Insight"
    assert "id" in result
    assert "created_at" in result

    # Verify card exists in DB
    cards = svc.list_cards(q="New Insight")
    assert len(cards) == 1


@pytest.mark.asyncio
async def test_save_insight_embedding_fails_card_still_saved():
    from alfred.mcp.tools import save_insight

    _, ctx, svc = _fixture()

    with patch(
        "alfred.services.zettelkasten_service.ZettelkastenService.ensure_embedding",
        side_effect=RuntimeError("No API key"),
    ):
        result = await save_insight(
            title="Insight Without Embedding",
            content="Embedding will fail",
            topic="test",
            ctx=ctx,
        )

    assert "error" not in result
    assert result["title"] == "Insight Without Embedding"

    # Card should still be in DB
    cards = svc.list_cards(q="Insight Without Embedding")
    assert len(cards) == 1


# ---------------------------------------------------------------------------
# _log_call
# ---------------------------------------------------------------------------


def test_log_call_writes_jsonl():
    from alfred.mcp.tools import _log_call

    with tempfile.TemporaryDirectory() as tmp:
        log_file = Path(tmp) / "mcp-sessions.jsonl"

        with patch("alfred.mcp.tools._LOG_DIR", Path(tmp)), patch(
            "alfred.mcp.tools._LOG_FILE", log_file
        ):
            _log_call("test-session", "search_knowledge", query="test", results_count=3)

        assert log_file.exists()
        line = json.loads(log_file.read_text().strip())
        assert line["tool"] == "search_knowledge"
        assert line["session_id"] == "test-session"
        assert line["results_count"] == 3
