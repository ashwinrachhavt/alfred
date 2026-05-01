from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from alfred.models.doc_storage import DocumentRow
from alfred.models.zettel import ZettelCard, ZettelReview
from alfred.services.today.entry_service import (
    ARTIFACT_KIND,
    EntriesPage,
    EntryService,
)


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _today() -> date:
    return date(2026, 4, 30)


# ---------------------------------------------------------------------------
# create_entry
# ---------------------------------------------------------------------------


def test_create_entry_persists_with_defaults(db_session: Session) -> None:
    svc = EntryService(db_session)
    row = svc.create_entry(entry_date=_today(), kind="todo", title="Write RFC")

    assert row.id is not None
    assert row.status == "open"
    assert row.priority == 0
    assert row.tags == []
    assert row.meta == {}
    assert row.body_md == ""
    assert row.title == "Write RFC"


def test_create_entry_rejects_invalid_kind(db_session: Session) -> None:
    svc = EntryService(db_session)
    with pytest.raises(ValueError, match="invalid kind"):
        svc.create_entry(entry_date=_today(), kind=ARTIFACT_KIND, title="X")
    with pytest.raises(ValueError, match="invalid kind"):
        svc.create_entry(entry_date=_today(), kind="bogus", title="X")


def test_create_entry_rejects_empty_title(db_session: Session) -> None:
    svc = EntryService(db_session)
    with pytest.raises(ValueError, match="title"):
        svc.create_entry(entry_date=_today(), kind="note", title="   ")


# ---------------------------------------------------------------------------
# list_entries: date range + filters
# ---------------------------------------------------------------------------


def test_list_entries_date_range_filters_out_of_range(db_session: Session) -> None:
    svc = EntryService(db_session)
    svc.create_entry(entry_date=date(2026, 4, 25), kind="todo", title="Old")
    svc.create_entry(entry_date=date(2026, 4, 30), kind="todo", title="Today")
    svc.create_entry(entry_date=date(2026, 5, 5), kind="todo", title="Future")

    page = svc.list_entries(
        start=date(2026, 4, 29),
        end=date(2026, 5, 1),
        include_artifacts=False,
    )
    titles = [e["title"] for e in page.entries]
    assert titles == ["Today"]
    assert page.total == 1


def test_list_entries_filters_by_kind_status_tags(db_session: Session) -> None:
    svc = EntryService(db_session)
    day = _today()
    svc.create_entry(entry_date=day, kind="todo", title="A", tags=["x", "y"])
    svc.create_entry(entry_date=day, kind="todo", title="B", tags=["x"], status="done")
    svc.create_entry(entry_date=day, kind="note", title="C", tags=["x", "y"])

    # kind filter
    page = svc.list_entries(start=day, end=day, kinds=["todo"], include_artifacts=False)
    assert {e["title"] for e in page.entries} == {"A", "B"}

    # status filter
    page = svc.list_entries(start=day, end=day, statuses=["done"], include_artifacts=False)
    assert {e["title"] for e in page.entries} == {"B"}

    # tags all-of semantics
    page = svc.list_entries(start=day, end=day, tags=["x", "y"], include_artifacts=False)
    assert {e["title"] for e in page.entries} == {"A", "C"}


def test_list_entries_q_substring_case_insensitive(db_session: Session) -> None:
    svc = EntryService(db_session)
    day = _today()
    svc.create_entry(entry_date=day, kind="note", title="DPO fundamentals")
    svc.create_entry(entry_date=day, kind="note", title="Other topic")

    page = svc.list_entries(start=day, end=day, q="dpo", include_artifacts=False)
    assert len(page.entries) == 1
    assert page.entries[0]["title"] == "DPO fundamentals"

    page = svc.list_entries(start=day, end=day, q="TOPIC", include_artifacts=False)
    assert len(page.entries) == 1
    assert page.entries[0]["title"] == "Other topic"


# ---------------------------------------------------------------------------
# update_entry / delete_entry
# ---------------------------------------------------------------------------


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def test_update_entry_applies_partial_patch_and_bumps_updated_at(
    db_session: Session,
) -> None:
    svc = EntryService(db_session)
    row = svc.create_entry(entry_date=_today(), kind="todo", title="Original")

    # Artificial backdating so the bump is detectable on fast CI clocks.
    backdated = datetime.now(UTC) - timedelta(minutes=5)
    row.updated_at = backdated
    db_session.add(row)
    db_session.commit()

    updated = svc.update_entry(
        row.id, patch={"title": "Revised", "status": "doing", "ignored_field": "X"}
    )
    assert updated.title == "Revised"
    assert updated.status == "doing"
    # Untouched fields preserved.
    assert updated.kind == "todo"
    assert updated.priority == 0
    # updated_at bumped vs the backdated value (normalize tz since SQLite drops it).
    updated_ts = _as_aware(updated.updated_at)
    assert updated_ts is not None
    assert updated_ts > backdated


def test_update_entry_on_missing_id_raises(db_session: Session) -> None:
    svc = EntryService(db_session)
    with pytest.raises(ValueError, match="not found"):
        svc.update_entry(99999, patch={"title": "x"})


def test_update_entry_rejects_invalid_kind_or_status(db_session: Session) -> None:
    svc = EntryService(db_session)
    row = svc.create_entry(entry_date=_today(), kind="todo", title="T")
    with pytest.raises(ValueError, match="invalid kind"):
        svc.update_entry(row.id, patch={"kind": "artifact_ref"})
    with pytest.raises(ValueError, match="invalid status"):
        svc.update_entry(row.id, patch={"status": "zombie"})


def test_delete_entry_returns_true_on_hit_false_on_miss(db_session: Session) -> None:
    svc = EntryService(db_session)
    row = svc.create_entry(entry_date=_today(), kind="note", title="disposable")

    assert svc.delete_entry(row.id) is True
    assert svc.get_entry(row.id) is None
    assert svc.delete_entry(row.id) is False
    assert svc.delete_entry(123456789) is False


# ---------------------------------------------------------------------------
# Artifact ref synthesis
# ---------------------------------------------------------------------------


def _make_document(created_at: datetime, *, title: str = "Doc") -> DocumentRow:
    now = datetime.now(UTC)
    return DocumentRow(
        id=uuid.uuid4(),
        source_url="https://example.com",
        canonical_url="https://example.com",
        domain="example.com",
        title=title,
        content_type="web",
        cleaned_text="hi",
        tokens=1,
        hash=str(uuid.uuid4()),
        day_bucket=created_at.date(),
        captured_at=created_at,
        captured_hour=created_at.astimezone(UTC).hour,
        processed_at=now,
        created_at=created_at,
        updated_at=now,
        tags=["captured"],
    )


def test_list_entries_include_artifacts_synthesizes_items(
    db_session: Session,
) -> None:
    svc = EntryService(db_session)
    day = _today()
    window_mid = datetime(2026, 4, 30, 15, 0, tzinfo=UTC)

    # Real entry on day
    svc.create_entry(entry_date=day, kind="todo", title="Ship it")

    # Zettel created on day
    card = ZettelCard(title="Jiang decomposition", created_at=window_mid)
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)

    # Document / capture on day
    doc = _make_document(window_mid, title="Paul Graham essay")
    db_session.add(doc)
    db_session.commit()

    # Review on day
    review = ZettelReview(card_id=card.id, stage=1, due_at=window_mid, created_at=window_mid)
    db_session.add(review)
    db_session.commit()

    page = svc.list_entries(start=day, end=day, include_artifacts=True, tz_name="UTC")

    titles = [e["title"] for e in page.entries]
    assert "Ship it" in titles
    assert any("Jiang decomposition" in t for t in titles)
    assert any("Paul Graham" in t for t in titles)
    assert any(t.startswith("Review:") for t in titles)

    synthetic_kinds = {e["meta"]["ref_kind"] for e in page.entries if e["is_synthetic"]}
    assert {"zettel", "capture", "review"}.issubset(synthetic_kinds)

    # Real entry carries is_synthetic=False and numeric id.
    real_items = [e for e in page.entries if not e["is_synthetic"]]
    assert len(real_items) == 1
    assert isinstance(real_items[0]["id"], int)


def test_list_entries_include_artifacts_false_excludes_synthetics(
    db_session: Session,
) -> None:
    svc = EntryService(db_session)
    day = _today()
    window_mid = datetime(2026, 4, 30, 15, 0, tzinfo=UTC)

    svc.create_entry(entry_date=day, kind="todo", title="Real only")
    card = ZettelCard(title="Drafts", created_at=window_mid)
    db_session.add(card)
    db_session.commit()

    page = svc.list_entries(start=day, end=day, include_artifacts=False)
    assert [e["is_synthetic"] for e in page.entries] == [False]
    assert page.entries[0]["title"] == "Real only"


def test_list_entries_kinds_excludes_artifact_ref(db_session: Session) -> None:
    svc = EntryService(db_session)
    day = _today()
    window_mid = datetime(2026, 4, 30, 15, 0, tzinfo=UTC)

    svc.create_entry(entry_date=day, kind="todo", title="Real todo")
    card = ZettelCard(title="Should not appear", created_at=window_mid)
    db_session.add(card)
    db_session.commit()

    page = svc.list_entries(start=day, end=day, kinds=["todo"])
    assert all(e["kind"] == "todo" for e in page.entries)
    assert all(not e["is_synthetic"] for e in page.entries)


# ---------------------------------------------------------------------------
# Tz edge case
# ---------------------------------------------------------------------------


def test_artifact_created_at_tz_local_date(db_session: Session) -> None:
    """2026-04-30 03:00 UTC is still 2026-04-29 in LA."""
    svc = EntryService(db_session)
    utc_moment = datetime(2026, 4, 30, 3, 0, tzinfo=UTC)

    card = ZettelCard(title="Night owl card", created_at=utc_moment)
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)

    # Query LA-local day 2026-04-29.
    page = svc.list_entries(
        start=date(2026, 4, 29),
        end=date(2026, 4, 29),
        tz_name="America/Los_Angeles",
        include_artifacts=True,
    )
    artifacts = [e for e in page.entries if e["is_synthetic"]]
    assert len(artifacts) >= 1
    matching = [e for e in artifacts if "Night owl" in e["title"]]
    assert matching, "expected night-owl zettel to surface on LA 2026-04-29"
    assert matching[0]["entry_date"] == "2026-04-29"

    # And NOT on 2026-04-30 LA.
    page2 = svc.list_entries(
        start=date(2026, 4, 30),
        end=date(2026, 4, 30),
        tz_name="America/Los_Angeles",
        include_artifacts=True,
    )
    assert not any("Night owl" in e["title"] for e in page2.entries)


# ---------------------------------------------------------------------------
# Returns-page shape
# ---------------------------------------------------------------------------


def test_list_entries_returns_entries_page(db_session: Session) -> None:
    svc = EntryService(db_session)
    svc.create_entry(entry_date=_today(), kind="todo", title="A")
    page = svc.list_entries(start=_today(), end=_today(), include_artifacts=False)
    assert isinstance(page, EntriesPage)
    assert isinstance(page.entries, list)
    assert page.next_cursor is None
    assert page.total == 1
