"""Commit reviewed zettel decomposition candidates."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from alfred.models.zettel import ZettelSession
from alfred.schemas.zettel import (
    BulkFromDecompositionRequest,
    BulkFromDecompositionResponse,
    DecomposeCandidateInput,
)
from alfred.services.session_service import SessionService
from alfred.services.zettelkasten_service import ZettelkastenService

MAX_DECOMPOSITION_BATCH = 50


class ZettelDecompositionCommitError(ValueError):
    """Raised when a decomposition commit request is invalid."""


@dataclass
class ZettelDecompositionCommitService:
    session: Session

    def commit(self, payload: BulkFromDecompositionRequest) -> BulkFromDecompositionResponse:
        """Persist candidates as cards and connect valid sibling links."""

        self._validate_payload(payload)
        self._validate_session(payload.session_id)

        svc = ZettelkastenService(self.session)
        cards = svc.create_cards_batch(self._cards_data(payload))
        card_ids = [int(card.id) for card in cards if card.id is not None]
        if len(card_ids) != len(payload.candidates):
            raise RuntimeError("Failed to create every decomposition card")

        link_count = self._create_sibling_links(
            svc=svc,
            card_ids=card_ids,
            candidates=payload.candidates,
        )
        self._touch_session(payload.session_id)

        return BulkFromDecompositionResponse(
            created_card_ids=card_ids,
            link_count=link_count,
        )

    @staticmethod
    def _validate_payload(payload: BulkFromDecompositionRequest) -> None:
        if len(payload.candidates) == 0:
            raise ZettelDecompositionCommitError("No candidates provided")
        if len(payload.candidates) > MAX_DECOMPOSITION_BATCH:
            raise ZettelDecompositionCommitError(
                f"Maximum {MAX_DECOMPOSITION_BATCH} candidates per commit"
            )

    def _validate_session(self, session_id: int | None) -> None:
        if session_id is None:
            return
        row = self.session.get(ZettelSession, session_id)
        if row is None:
            raise ZettelDecompositionCommitError("Session not found")
        if row.ended_at is not None:
            raise ZettelDecompositionCommitError("Session has already ended")

    @staticmethod
    def _cards_data(payload: BulkFromDecompositionRequest) -> list[dict]:
        return [
            {
                "title": candidate.title,
                "content": candidate.content,
                "bloom_level": candidate.bloom_level,
                "bloom_source": "ai_inferred",
                "tags": candidate.tags or [],
                "topic": payload.shared_topic,
                "source_url": payload.source_url,
                "session_id": payload.session_id,
            }
            for candidate in payload.candidates
        ]

    @staticmethod
    def _create_sibling_links(
        *,
        svc: ZettelkastenService,
        card_ids: list[int],
        candidates: list[DecomposeCandidateInput],
    ) -> int:
        link_count = 0
        candidate_count = len(candidates)
        for source_index, candidate in enumerate(candidates):
            seen: set[int] = set()
            for target_index in candidate.links_to_siblings or []:
                if not isinstance(target_index, int):
                    continue
                if target_index < 0 or target_index >= candidate_count:
                    continue
                if target_index == source_index or target_index in seen:
                    continue
                seen.add(target_index)
                svc.create_link(
                    from_card_id=card_ids[source_index],
                    to_card_id=card_ids[target_index],
                    type="decomposition_sibling",
                    bidirectional=True,
                )
                link_count += 1
        return link_count

    def _touch_session(self, session_id: int | None) -> None:
        if session_id is None:
            return
        try:
            SessionService(self.session).touch(session_id)
        except Exception:
            # Activity touch is best-effort metadata; the cards and links are
            # already committed and should remain the source of truth.
            return
