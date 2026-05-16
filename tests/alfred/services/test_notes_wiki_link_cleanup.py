from __future__ import annotations

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

from alfred.models.zettel import WikiLink, ZettelCard
from alfred.services.notes_service import NotesService
from alfred.services.zettelkasten_service import ZettelkastenService


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_archive_note_drops_owned_wiki_links() -> None:
    session = _session()
    zk = ZettelkastenService(session)
    notes = NotesService(session)

    target_a = zk.create_card(title="Heisenberg")
    target_b = zk.create_card(title="Bohr")

    note = notes.create_note(title="Quantum", user_id=None)
    zk.sync_wiki_links(
        source_type="note",
        source_id=str(note.id),
        target_card_ids=[target_a.id, target_b.id],
    )

    pre = list(
        session.exec(
            select(WikiLink).where(
                (WikiLink.source_type == "note") & (WikiLink.source_id == str(note.id))
            )
        )
    )
    assert len(pre) == 2

    notes.archive_note(note.id)

    post = list(
        session.exec(
            select(WikiLink).where(
                (WikiLink.source_type == "note") & (WikiLink.source_id == str(note.id))
            )
        )
    )
    assert post == []


def test_archive_note_does_not_touch_other_sources() -> None:
    """Regression guard: archiving a note must not delete wiki_links owned
    by other sources (zettel sources, or wiki_links from a different note).
    """
    session = _session()
    zk = ZettelkastenService(session)
    notes = NotesService(session)

    target = zk.create_card(title="Shared target")

    note_a = notes.create_note(title="Note A", user_id=None)
    note_b = notes.create_note(title="Note B", user_id=None)

    zk.sync_wiki_links(
        source_type="note", source_id=str(note_a.id), target_card_ids=[target.id]
    )
    zk.sync_wiki_links(
        source_type="note", source_id=str(note_b.id), target_card_ids=[target.id]
    )
    zk.sync_wiki_links(
        source_type="zettel", source_id="999", target_card_ids=[target.id]
    )

    notes.archive_note(note_a.id)

    remaining = list(session.exec(select(WikiLink)))
    sources = sorted((wl.source_type, wl.source_id) for wl in remaining)
    assert sources == [("note", str(note_b.id)), ("zettel", "999")]
