from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from alfred.services.zettelkasten_service import ZettelkastenService


@dataclass
class ZettelEmbeddingService:
    """
    Back-compat wrapper. Prefer `alfred.services.zettelkasten_service.ZettelkastenService`.
    """

    session: Session

    def __post_init__(self) -> None:
        self._svc = ZettelkastenService(self.session)

    def embed_card(self, card):  # noqa: ANN001
        return self._svc.embed_card(card)

    def ensure_embedding(self, card):  # noqa: ANN001
        return self._svc.ensure_embedding(card)

    def find_similar_cards(self, card_id: int, *, threshold: float = 0.7, limit: int = 10):
        return self._svc.find_similar_cards(card_id, threshold=threshold, limit=limit)

    def suggest_links(self, card_id: int, *, min_confidence: float = 0.6, limit: int = 10):
        return self._svc.suggest_links(card_id, min_confidence=min_confidence, limit=limit)


__all__ = ["ZettelEmbeddingService"]
