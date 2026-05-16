"""Tests for the agent's create_note and update_note tools.

These exercise the wiki-link sync path that runs server-side when the agent
authors notes (the editor-driven flow uses a different code path that lives
in the frontend).
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

from alfred.models.zettel import WikiLink
from alfred.services.agent.tools import (
    _create_note,
    _extract_wiki_link_titles,
    _update_note,
)
from alfred.services.zettelkasten_service import ZettelkastenService


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


# ---------------------------------------------------------------------------
# _extract_wiki_link_titles — pure function tests
# ---------------------------------------------------------------------------


def test_extract_titles_basic() -> None:
    assert _extract_wiki_link_titles("see [[Heisenberg]]") == ["Heisenberg"]


def test_extract_titles_strips_alias_pipe() -> None:
    """[[X|alias]] returns 'X', not the alias."""
    assert _extract_wiki_link_titles("[[Heisenberg|the man]]") == ["Heisenberg"]


def test_extract_titles_dedupes_case_insensitive() -> None:
    titles = _extract_wiki_link_titles("[[Bohr]] and again [[Bohr]] and [[bohr]]")
    # Implementation dedupes by lowercased form, preserves first-seen casing.
    assert titles == ["Bohr"]


def test_extract_titles_handles_none_and_empty() -> None:
    assert _extract_wiki_link_titles(None) == []
    assert _extract_wiki_link_titles("") == []
    assert _extract_wiki_link_titles("no links here") == []


def test_extract_titles_skips_empty_brackets() -> None:
    assert _extract_wiki_link_titles("[[]] and [[   ]]") == []


# ---------------------------------------------------------------------------
# create_note / update_note — wiki-link sync integration
# ---------------------------------------------------------------------------


def _existing_note_links(session: Session, note_id: str) -> set[int]:
    rows = list(
        session.exec(
            select(WikiLink).where(
                (WikiLink.source_type == "note") & (WikiLink.source_id == note_id)
            )
        )
    )
    return {wl.target_card_id for wl in rows}


def test_create_note_resolves_wiki_links_to_existing_zettels() -> None:
    session = _session()
    zk = ZettelkastenService(session)
    a = zk.create_card(title="Heisenberg")
    b = zk.create_card(title="Bohr")
    zk.create_card(title="Schrodinger")  # not referenced

    result = asyncio.run(
        _create_note(
            {
                "title": "Quantum stuff",
                "content_markdown": "I read [[Heisenberg]] and [[Bohr]]",
            },
            session,
        )
    )

    assert result["action"] == "created"
    assert result["wiki_link_count"] == 2
    note_id = result["note_id"]
    assert _existing_note_links(session, note_id) == {a.id, b.id}


def test_create_note_unresolved_wiki_links_synced_as_empty() -> None:
    """Tokens that don't match any zettel produce zero wiki_links rows
    but the note still saves cleanly."""
    session = _session()
    result = asyncio.run(
        _create_note(
            {
                "title": "Unknown refs",
                "content_markdown": "[[Nobody]] referenced here",
            },
            session,
        )
    )
    assert result["action"] == "created"
    assert result["wiki_link_count"] == 0
    assert _existing_note_links(session, result["note_id"]) == set()


def test_update_note_resyncs_wiki_links_on_content_change() -> None:
    """Removing [[Bohr]] and adding [[Schrodinger]] must drop the Bohr edge
    and add the Schrodinger one — diff-based, not append-only."""
    session = _session()
    zk = ZettelkastenService(session)
    a = zk.create_card(title="Heisenberg")
    b = zk.create_card(title="Bohr")
    c = zk.create_card(title="Schrodinger")

    created = asyncio.run(
        _create_note(
            {
                "title": "Quantum",
                "content_markdown": "[[Heisenberg]] and [[Bohr]]",
            },
            session,
        )
    )
    assert _existing_note_links(session, created["note_id"]) == {a.id, b.id}

    updated = asyncio.run(
        _update_note(
            {
                "note_id": created["note_id"],
                "content_markdown": "[[Heisenberg]] and [[Schrodinger]]",
            },
            session,
        )
    )
    assert updated["action"] == "updated"
    assert updated["wiki_link_count"] == 2
    assert _existing_note_links(session, created["note_id"]) == {a.id, c.id}


def test_update_note_without_content_preserves_existing_wiki_links() -> None:
    """If the agent updates only the title, wiki_links should not be wiped."""
    session = _session()
    zk = ZettelkastenService(session)
    a = zk.create_card(title="Heisenberg")

    created = asyncio.run(
        _create_note(
            {"title": "Quantum", "content_markdown": "[[Heisenberg]]"},
            session,
        )
    )
    assert _existing_note_links(session, created["note_id"]) == {a.id}

    asyncio.run(
        _update_note(
            {"note_id": created["note_id"], "title": "New title"},
            session,
        )
    )

    # Wiki-links resync runs from row.content_markdown which is unchanged,
    # so the same edge stays present.
    assert _existing_note_links(session, created["note_id"]) == {a.id}


def test_create_note_missing_title_returns_error() -> None:
    session = _session()
    result = asyncio.run(_create_note({"content_markdown": "x"}, session))
    assert "error" in result


def test_update_note_missing_id_returns_error() -> None:
    session = _session()
    result = asyncio.run(_update_note({"title": "x"}, session))
    assert "error" in result
