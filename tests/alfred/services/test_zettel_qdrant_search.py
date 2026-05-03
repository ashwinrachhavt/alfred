# tests/alfred/services/test_zettel_qdrant_search.py
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch


def _make_mock_card(card_id: int) -> MagicMock:
    """Create a mock ZettelCard with all attributes _quality needs."""
    card = MagicMock()
    card.id = card_id
    card.embedding = [0.1 * card_id] * 1536
    card.topics = []
    card.tags = []
    card.topic = None
    card.document_id = None
    card.source_url = None
    card.updated_at = datetime(2026, 1, 1)
    return card


def test_find_similar_cards_uses_qdrant_when_available():
    """Qdrant primary path: hits are batch-fetched from SQL via a single `id IN (...)`
    query (no full-table scan, no per-hit session.get).
    """
    from alfred.services.zettelkasten_service import ZettelkastenService

    session = MagicMock()
    svc = ZettelkastenService(session=session)

    mock_card = _make_mock_card(1)
    mock_cand = _make_mock_card(2)

    def side_get(model_or_id, pk=None):
        if pk is None:
            pk = model_or_id
        return {1: mock_card, 2: mock_cand}.get(pk)

    session.get.side_effect = side_get

    # session.exec is called twice: once by _existing_links (returns empty links),
    # once by the batched candidate fetch (returns the hydrated candidate rows).
    existing_links_result = MagicMock()
    existing_links_result.__iter__ = lambda self: iter([])
    candidates_result = MagicMock()
    candidates_result.all.return_value = [mock_cand]
    session.exec.side_effect = [existing_links_result, candidates_result]

    mock_qdrant = MagicMock()
    mock_hit = MagicMock()
    mock_hit.id = 2
    mock_hit.score = 0.85
    mock_qdrant.query_points.return_value.points = [mock_hit]

    with patch(
        "alfred.services.zettelkasten_service.get_qdrant_client",
        return_value=mock_qdrant,
    ):
        svc.find_similar_cards(1, threshold=0.5, limit=5)

    mock_qdrant.query_points.assert_called_once()
    # Two calls: _existing_links + batched candidate fetch (no per-hit session.get).
    assert session.exec.call_count == 2


def test_find_similar_cards_falls_back_without_qdrant():
    """When Qdrant unavailable, use Python cosine similarity fallback."""
    from alfred.services.zettelkasten_service import ZettelkastenService

    session = MagicMock()
    svc = ZettelkastenService(session=session)

    mock_card = _make_mock_card(1)
    session.get.return_value = mock_card
    # Two exec calls: _existing_links (returns links) + _find_similar_via_scan (returns candidates)
    session.exec.return_value = iter([])

    with patch(
        "alfred.services.zettelkasten_service.get_qdrant_client",
        return_value=None,
    ):
        results = svc.find_similar_cards(1, threshold=0.5, limit=5)

    # Called twice: once for _existing_links, once for candidate scan
    assert session.exec.call_count == 2
    assert results == []
