"""Regression tests for the T1 Zettel session + Bloom migration.

Covers:
    * ``ZettelSession.status`` property derivation (D4).
    * ``ZettelSession`` default ``card_count == 0``.
    * Running the new migration's ``upgrade()`` against a pre-T1
      ``zettel_cards`` schema: a pre-existing row is deterministically
      backfilled to ``bloom_level=1`` / ``bloom_source='backfill'`` (D2),
      and all other new columns are NULL.

Why we don't run the full migration chain here:
    Earlier migrations contain Postgres-specific DDL (``CREATE EXTENSION``,
    ``ALTER TABLE ... SET``) that SQLite can't execute, so replaying the
    whole chain would be a porting project. Instead we build a minimal
    "pre-T1" zettel_cards table matching production's shape, stamp the
    alembic version to the previous head, and then run ``alembic upgrade``
    for just our migration. That exercises the real upgrade() we're shipping.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from alfred.core.settings import settings
from alfred.models.zettel import ZettelSession

# ---------------------------------------------------------------------------
# Schema-level tests (no DB required)
# ---------------------------------------------------------------------------


def test_zettel_session_status_derivation() -> None:
    """Status is derived from ``ended_at`` + ``summary_card_id`` (D4)."""

    now = datetime(2026, 5, 1, 12, 0, 0)

    # active: ended_at is None
    s = ZettelSession(title="A")
    assert s.ended_at is None
    assert s.status == "active"

    # ended: ended_at set AND summary_card_id set
    s = ZettelSession(title="B", ended_at=now, summary_card_id=42)
    assert s.status == "ended"

    # abandoned: ended_at set, summary_card_id still None
    s = ZettelSession(title="C", ended_at=now, summary_card_id=None)
    assert s.status == "abandoned"


def test_zettel_session_card_count_field_default_zero() -> None:
    """Freshly instantiated sessions start with ``card_count == 0``."""

    s = ZettelSession()
    assert s.card_count == 0


# ---------------------------------------------------------------------------
# Migration upgrade test
# ---------------------------------------------------------------------------


_REPO_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"
_SCRIPT_LOCATION = _REPO_ROOT / "apps" / "alfred" / "migrations"

PREV_HEAD = "i3j4k5l6m7n8"
NEW_HEAD = "a1b2c3d4e5f7"


def _make_alembic_config(db_url: str) -> Config:
    """Build an Alembic Config pointing at ``db_url``."""

    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_SCRIPT_LOCATION))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _build_pre_t1_schema(engine) -> None:
    """Build a minimal pre-T1 schema with just the ``zettel_cards`` table.

    Mirrors the ``ZettelCard`` columns as they existed before T1 added the
    six new columns. Uses SQLite-safe types.
    """

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE zettel_cards ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "created_at DATETIME, "
                "updated_at DATETIME, "
                "title VARCHAR(255) NOT NULL, "
                "content TEXT, "
                "summary TEXT, "
                "tags TEXT, "
                "topic VARCHAR(128), "
                "source_url VARCHAR(2048), "
                "document_id VARCHAR(96), "
                "status VARCHAR(32) NOT NULL, "
                "importance INTEGER NOT NULL, "
                "confidence REAL NOT NULL, "
                "embedding TEXT"
                ")"
            )
        )
        # alembic_version table + pin to the previous head so upgrade()
        # finds exactly one revision to apply.
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
        )
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:v)"),
            {"v": PREV_HEAD},
        )


def test_migration_backfills_all_existing_cards_bloom_1_backfill_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run ``upgrade()`` for ``a1b2c3d4e5f7`` on a pre-T1 DB and verify backfill.

    Steps:
        1. Create a SQLite DB with *only* the pre-T1 ``zettel_cards`` table
           (no new columns) and stamp it to the previous head.
        2. Insert one ZettelCard row via raw SQL.
        3. Run ``alembic upgrade head`` — this runs only our migration.
        4. Assert the pre-existing row has ``bloom_level=1``,
           ``bloom_source='backfill'`` (D2), and all other new columns NULL.
        5. Assert the ``zettel_sessions`` table exists.
    """

    db_path = tmp_path / "migration_test.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setattr(settings, "database_url", db_url)

    engine = create_engine(db_url, future=True)

    # Step 1: fabricate the pre-T1 schema.
    _build_pre_t1_schema(engine)

    # Step 2: insert a pre-existing card (using raw SQL so the ORM's new
    # columns don't leak into the insert).
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO zettel_cards "
                "(title, status, importance, confidence) "
                "VALUES (:title, :status, :importance, :confidence)"
            ),
            {
                "title": "Pre-existing Card",
                "status": "active",
                "importance": 0,
                "confidence": 0.0,
            },
        )

        # Sanity check: pre-migration schema must not have the new columns.
        pragma_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info('zettel_cards')")).all()
        }
        for new_col in (
            "session_id",
            "bloom_level",
            "bloom_source",
            "bloom_history",
            "enrichment_attempted_at",
            "enrichment_last_error",
        ):
            assert new_col not in pragma_cols, (
                f"Pre-migration schema unexpectedly already has column {new_col!r}"
            )

    engine.dispose()

    cfg = _make_alembic_config(db_url)

    # Step 3: run alembic upgrade — only our migration should apply because
    # the version table is stamped at PREV_HEAD.
    command.upgrade(cfg, NEW_HEAD)

    # Step 4: verify backfill on the pre-existing row.
    engine = create_engine(db_url, future=True)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT session_id, bloom_level, bloom_source, bloom_history, "
                "enrichment_attempted_at, enrichment_last_error "
                "FROM zettel_cards WHERE title = :title"
            ),
            {"title": "Pre-existing Card"},
        ).one()

        (
            session_id,
            bloom_level,
            bloom_source,
            bloom_history,
            enrichment_attempted_at,
            enrichment_last_error,
        ) = row

        assert session_id is None, "Pre-existing card should not have a session_id"
        assert bloom_level == 1, "Backfill must set bloom_level to 1 (D2)"
        assert bloom_source == "backfill", "Backfill must set bloom_source to 'backfill' (D2)"
        assert bloom_history is None
        assert enrichment_attempted_at is None
        assert enrichment_last_error is None

        # Step 5: the zettel_sessions table exists and is empty.
        count = conn.execute(text("SELECT COUNT(*) FROM zettel_sessions")).scalar_one()
        assert count == 0

        # And alembic_version now points at the new head.
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version == NEW_HEAD
