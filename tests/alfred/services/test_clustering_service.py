"""Tests for ClusteringService — clustering, gap detection, and caching."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import numpy as np

from alfred.services.clustering_service import ClusteringService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class _FakeCard:
    """Minimal stand-in for ZettelCard used by the clustering service."""
    id: int
    title: str
    status: str = "active"
    embedding: list[float] | None = None


@dataclass
class _FakeLink:
    """Minimal stand-in for ZettelLink."""
    from_card_id: int
    to_card_id: int


def _make_cards_with_embeddings(n: int, dim: int = 8) -> list[_FakeCard]:
    """Create *n* fake cards with distinct random embeddings."""
    rng = np.random.RandomState(42)
    cards = []
    for i in range(n):
        vec = rng.randn(dim).tolist()
        cards.append(_FakeCard(id=i + 1, title=f"Card {i + 1}", embedding=vec))
    return cards


# ---------------------------------------------------------------------------
# detect_clusters
# ---------------------------------------------------------------------------


class TestDetectClusters:
    def test_fewer_than_10_cards_returns_empty(self) -> None:
        cards = _make_cards_with_embeddings(5)
        svc = ClusteringService()
        result = svc.detect_clusters(cards)
        assert result == []

    def test_20_cards_returns_at_least_2_clusters(self) -> None:
        cards = _make_cards_with_embeddings(20)
        svc = ClusteringService()
        result = svc.detect_clusters(cards)
        assert len(result) >= 2
        # Each cluster dict should have the required keys
        for cluster in result:
            assert "id" in cluster
            assert "name" in cluster
            assert "card_ids" in cluster
            assert "color" in cluster
            assert len(cluster["card_ids"]) > 0

    def test_cards_without_embeddings_are_excluded(self) -> None:
        """12 cards total but only 8 have embeddings → below threshold → empty."""
        cards_with = _make_cards_with_embeddings(8)
        cards_without = [_FakeCard(id=100 + i, title=f"No Embed {i}") for i in range(4)]
        svc = ClusteringService()
        result = svc.detect_clusters(cards_with + cards_without)
        # Only 8 embeddable cards — below the minimum of 10
        assert result == []

    def test_cards_without_embeddings_excluded_but_enough_remain(self) -> None:
        """15 cards with embeddings + 5 without → 15 valid → clusters returned."""
        cards_with = _make_cards_with_embeddings(15)
        cards_without = [_FakeCard(id=200 + i, title=f"No Embed {i}") for i in range(5)]
        svc = ClusteringService()
        result = svc.detect_clusters(cards_with + cards_without)
        assert len(result) >= 2
        # No card_id from the embedding-less cards should appear
        all_clustered_ids: set[int] = set()
        for c in result:
            all_clustered_ids.update(c["card_ids"])
        for card in cards_without:
            assert card.id not in all_clustered_ids

    def test_cluster_colors_are_hex_strings(self) -> None:
        cards = _make_cards_with_embeddings(20)
        svc = ClusteringService()
        result = svc.detect_clusters(cards)
        for cluster in result:
            assert cluster["color"].startswith("#")
            assert len(cluster["color"]) == 7  # #RRGGBB


# ---------------------------------------------------------------------------
# detect_knowledge_gaps
# ---------------------------------------------------------------------------


class TestDetectKnowledgeGaps:
    def test_finds_stubs_with_inbound_links(self) -> None:
        stub = _FakeCard(id=1, title="Stub Card", status="stub")
        active = _FakeCard(id=2, title="Active Card", status="active")
        links = [
            _FakeLink(from_card_id=2, to_card_id=1),
            _FakeLink(from_card_id=3, to_card_id=1),
        ]
        svc = ClusteringService()
        gaps = svc.detect_knowledge_gaps([stub, active], links)
        assert len(gaps) == 1
        assert gaps[0]["id"] == 1
        assert gaps[0]["title"] == "Stub Card"
        assert gaps[0]["inbound_link_count"] == 2

    def test_returns_empty_when_no_stubs(self) -> None:
        cards = [
            _FakeCard(id=1, title="Active 1", status="active"),
            _FakeCard(id=2, title="Active 2", status="active"),
        ]
        links = [_FakeLink(from_card_id=1, to_card_id=2)]
        svc = ClusteringService()
        gaps = svc.detect_knowledge_gaps(cards, links)
        assert gaps == []

    def test_stub_without_inbound_links_not_a_gap(self) -> None:
        stub = _FakeCard(id=1, title="Orphan Stub", status="stub")
        svc = ClusteringService()
        gaps = svc.detect_knowledge_gaps([stub], [])
        assert gaps == []


# ---------------------------------------------------------------------------
# invalidate_cache
# ---------------------------------------------------------------------------


class TestInvalidateCache:
    @patch("alfred.services.clustering_service.get_redis_client")
    def test_invalidate_cache_deletes_key(self, mock_get_redis: MagicMock) -> None:
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        ClusteringService.invalidate_cache()
        mock_redis.delete.assert_called_once_with("zettel:graph:clusters")

    @patch("alfred.services.clustering_service.get_redis_client")
    def test_invalidate_cache_handles_no_redis(self, mock_get_redis: MagicMock) -> None:
        mock_get_redis.return_value = None
        # Should not raise — gracefully handles missing Redis
        ClusteringService.invalidate_cache()


# ---------------------------------------------------------------------------
# generate_cluster_names
# ---------------------------------------------------------------------------


class TestGenerateClusterNames:
    @patch("alfred.services.clustering_service.get_chat_model")
    def test_names_clusters_via_llm(self, mock_get_model: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content="Machine Learning")
        mock_get_model.return_value = mock_model

        clusters = [{"id": 0, "name": "Cluster 0", "card_ids": [1, 2], "color": "#FFB088"}]
        cards_by_id = {
            1: _FakeCard(id=1, title="Neural Networks"),
            2: _FakeCard(id=2, title="Deep Learning"),
        }
        svc = ClusteringService()
        result = svc.generate_cluster_names(clusters, cards_by_id)
        assert result[0]["name"] == "Machine Learning"

    @patch("alfred.services.clustering_service.get_chat_model")
    def test_handles_llm_failure_gracefully(self, mock_get_model: MagicMock) -> None:
        mock_get_model.side_effect = Exception("LLM unavailable")

        clusters = [{"id": 0, "name": "Cluster 0", "card_ids": [1], "color": "#FFB088"}]
        cards_by_id = {1: _FakeCard(id=1, title="Some Card")}
        svc = ClusteringService()
        result = svc.generate_cluster_names(clusters, cards_by_id)
        # Should return clusters unchanged (unnamed) without raising
        assert result[0]["name"] == "Cluster 0"


# ---------------------------------------------------------------------------
# _cluster_color
# ---------------------------------------------------------------------------


class TestClusterColor:
    def test_single_cluster_returns_start_color(self) -> None:
        color = ClusteringService._cluster_color(0, 1)
        assert color == "#FFB088"

    def test_gradient_endpoints(self) -> None:
        start = ClusteringService._cluster_color(0, 5)
        end = ClusteringService._cluster_color(4, 5)
        assert start == "#FFB088"
        assert end == "#C44600"

    def test_returns_valid_hex(self) -> None:
        for i in range(10):
            color = ClusteringService._cluster_color(i, 10)
            assert color.startswith("#")
            assert len(color) == 7
