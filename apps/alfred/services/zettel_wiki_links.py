"""Wiki-link syncing and backlink aggregation for zettel cards."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlmodel import Session, select

from alfred.models.notes import NoteRow
from alfred.models.zettel import WikiLink, ZettelCard, ZettelLink


@dataclass
class ZettelWikiLinkService:
    """Manage editor wiki-links and backlink read models."""

    session: Session

    def list_backlinks(self, card_id: int) -> list[dict]:
        """Return wiki-links and graph links pointing to a card."""
        backlinks: list[dict] = []
        wiki_rows = list(
            self.session.exec(select(WikiLink).where(WikiLink.target_card_id == card_id))
        )

        zettel_titles = self._zettel_source_titles(wiki_rows)
        note_titles = self._note_source_titles(wiki_rows)

        for wiki_link in wiki_rows:
            if wiki_link.source_type == "zettel":
                source_title = zettel_titles.get(int(wiki_link.source_id), "Unknown")
            elif wiki_link.source_type == "note":
                source_title = note_titles.get(wiki_link.source_id, "Unknown")
            else:
                source_title = "Unknown"
            backlinks.append(
                {
                    "source_type": wiki_link.source_type,
                    "source_id": wiki_link.source_id,
                    "source_title": source_title,
                    "created_at": wiki_link.created_at,
                }
            )

        backlinks.extend(self._incoming_graph_backlinks(card_id, backlinks))
        return backlinks

    def sync_wiki_links(
        self,
        *,
        source_type: str,
        source_id: str,
        target_card_ids: list[int],
    ) -> None:
        """Replace wiki-link targets for a source document."""
        existing = list(
            self.session.exec(
                select(WikiLink).where(
                    (WikiLink.source_type == source_type) & (WikiLink.source_id == source_id)
                )
            )
        )
        existing_targets = {wiki_link.target_card_id: wiki_link for wiki_link in existing}
        desired_targets = set(target_card_ids)

        for target_id, wiki_link in existing_targets.items():
            if target_id not in desired_targets:
                self.session.delete(wiki_link)

        for target_id in desired_targets:
            if target_id not in existing_targets:
                self.session.add(
                    WikiLink(
                        source_type=source_type,
                        source_id=source_id,
                        target_card_id=target_id,
                    )
                )

        self.session.commit()

    def _zettel_source_titles(self, wiki_rows: list[WikiLink]) -> dict[int, str]:
        source_ids = [
            int(wiki_link.source_id)
            for wiki_link in wiki_rows
            if wiki_link.source_type == "zettel"
        ]
        if not source_ids:
            return {}
        cards = self.session.exec(
            select(ZettelCard).where(ZettelCard.id.in_(source_ids))  # type: ignore[union-attr]
        )
        return {card.id: card.title for card in cards if card.id is not None}

    def _note_source_titles(self, wiki_rows: list[WikiLink]) -> dict[str, str]:
        note_uuids = []
        for wiki_link in wiki_rows:
            if wiki_link.source_type != "note":
                continue
            try:
                note_uuids.append(uuid.UUID(wiki_link.source_id))
            except (ValueError, TypeError):
                pass
        if not note_uuids:
            return {}
        notes = self.session.exec(
            select(NoteRow).where(NoteRow.id.in_(note_uuids))  # type: ignore[attr-defined]
        )
        return {str(note.id): note.title for note in notes}

    def _incoming_graph_backlinks(
        self,
        card_id: int,
        existing_backlinks: list[dict],
    ) -> list[dict]:
        incoming = list(
            self.session.exec(select(ZettelLink).where(ZettelLink.to_card_id == card_id))
        )
        seen_card_ids = self._seen_zettel_source_ids(existing_backlinks)
        incoming_card_ids = [
            link.from_card_id for link in incoming if link.from_card_id not in seen_card_ids
        ]

        incoming_titles: dict[int, str] = {}
        if incoming_card_ids:
            cards = self.session.exec(
                select(ZettelCard).where(ZettelCard.id.in_(incoming_card_ids))  # type: ignore[union-attr]
            )
            incoming_titles = {card.id: card.title for card in cards if card.id is not None}

        backlinks: list[dict] = []
        for link in incoming:
            if link.from_card_id in seen_card_ids:
                continue
            title = incoming_titles.get(link.from_card_id)
            if title:
                backlinks.append(
                    {
                        "source_type": "zettel",
                        "source_id": str(link.from_card_id),
                        "source_title": title,
                        "created_at": link.created_at,
                    }
                )
        return backlinks

    @staticmethod
    def _seen_zettel_source_ids(backlinks: list[dict]) -> set[int]:
        seen: set[int] = set()
        for backlink in backlinks:
            if backlink["source_type"] != "zettel":
                continue
            try:
                seen.add(int(backlink["source_id"]))
            except (ValueError, TypeError):
                pass
        return seen
