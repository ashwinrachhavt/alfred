"""Clustering service for 3D Knowledge Universe visualization.

Groups zettel cards into semantic clusters using KMeans on card embeddings,
generates human-readable cluster names via LLM, and detects knowledge gaps
(stub cards with inbound links).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.cluster import KMeans

from alfred.core.llm_factory import get_chat_model
from alfred.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

_CACHE_KEY = "zettel:graph:clusters"
_MIN_CARDS_FOR_CLUSTERING = 10


@dataclass
class ClusteringService:
    """Clusters zettel cards and detects knowledge gaps."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_clusters(self, cards: list[Any]) -> list[dict[str, Any]]:
        """Run KMeans clustering on card embeddings.

        Args:
            cards: Objects with ``id``, ``title``, and optional ``embedding`` attrs.

        Returns:
            List of cluster dicts with keys: id, name, card_ids, color.
            Empty list when fewer than *_MIN_CARDS_FOR_CLUSTERING* embeddable
            cards are provided.
        """
        # Filter to cards that have embeddings
        embeddable: list[tuple[Any, list[float]]] = []
        excluded = 0
        for card in cards:
            emb = getattr(card, "embedding", None)
            if emb is not None and len(emb) > 0:
                embeddable.append((card, emb))
            else:
                excluded += 1

        if excluded:
            logger.warning(
                "Excluded %d card(s) without embeddings from clustering", excluded
            )

        n = len(embeddable)
        if n < _MIN_CARDS_FOR_CLUSTERING:
            return []

        # Build matrix and run KMeans
        X = np.array([emb for _, emb in embeddable])
        k = max(2, n // 10)
        kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
        labels = kmeans.fit_predict(X)

        # Group card IDs by cluster label
        cluster_map: dict[int, list[int]] = {}
        for idx, label in enumerate(labels):
            label_int = int(label)
            card = embeddable[idx][0]
            cluster_map.setdefault(label_int, []).append(card.id)

        total = len(cluster_map)
        clusters: list[dict[str, Any]] = []
        for cluster_id in sorted(cluster_map):
            clusters.append(
                {
                    "id": cluster_id,
                    "name": f"Cluster {cluster_id}",
                    "card_ids": cluster_map[cluster_id],
                    "color": self._cluster_color(cluster_id, total),
                }
            )

        return clusters

    def generate_cluster_names(
        self,
        clusters: list[dict[str, Any]],
        cards_by_id: dict[int, Any],
    ) -> list[dict[str, Any]]:
        """Use an LLM to generate a 2-4 word name for each cluster.

        Falls back to the existing placeholder name if the LLM is unavailable.
        """
        try:
            model = get_chat_model()
        except Exception:
            logger.warning("LLM unavailable — returning unnamed clusters")
            return clusters

        named: list[dict[str, Any]] = []
        for cluster in clusters:
            titles = [
                getattr(cards_by_id.get(cid), "title", str(cid))
                for cid in cluster["card_ids"]
            ]
            prompt = (
                "Given these knowledge card titles, generate a concise 2-4 word "
                "cluster name that captures the common theme. Reply with ONLY the "
                "cluster name, nothing else.\n\n"
                f"Titles: {', '.join(titles)}"
            )
            try:
                response = model.invoke(prompt)
                name = response.content.strip() if response.content else cluster["name"]
            except Exception:
                logger.warning(
                    "LLM call failed for cluster %s — keeping placeholder name",
                    cluster["id"],
                )
                name = cluster["name"]

            named.append({**cluster, "name": name})

        return named

    def detect_knowledge_gaps(
        self,
        cards: list[Any],
        links: list[Any],
    ) -> list[dict[str, Any]]:
        """Find stub cards that have inbound links (knowledge gaps).

        Args:
            cards: Objects with ``id``, ``title``, ``status`` attrs.
            links: Objects with ``from_card_id``, ``to_card_id`` attrs.

        Returns:
            List of gap dicts with keys: id, title, inbound_link_count.
        """
        # Identify stub card IDs
        stub_ids: set[int] = set()
        title_by_id: dict[int, str] = {}
        for card in cards:
            if getattr(card, "status", None) == "stub":
                stub_ids.add(card.id)
                title_by_id[card.id] = getattr(card, "title", "")

        if not stub_ids:
            return []

        # Count inbound links to stubs
        inbound_counts: dict[int, int] = {}
        for link in links:
            target = link.to_card_id
            if target in stub_ids:
                inbound_counts[target] = inbound_counts.get(target, 0) + 1

        gaps: list[dict[str, Any]] = []
        for card_id, count in sorted(inbound_counts.items(), key=lambda x: -x[1]):
            gaps.append(
                {
                    "id": card_id,
                    "title": title_by_id.get(card_id, ""),
                    "inbound_link_count": count,
                }
            )

        return gaps

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    @staticmethod
    def invalidate_cache() -> None:
        """Delete the Redis cache key for graph clusters."""
        redis = get_redis_client()
        if redis is None:
            return
        try:
            redis.delete(_CACHE_KEY)
        except Exception:
            logger.warning("Failed to invalidate cluster cache key %s", _CACHE_KEY)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cluster_color(idx: int, total: int) -> str:
        """Return a hex color from a monochrome orange gradient.

        Interpolates from #FFB088 (light) at idx=0 to #C44600 (dark) at
        idx=total-1.
        """
        if total <= 1:
            return "#FFB088"

        t = idx / (total - 1)

        # Start: #FFB088 → (255, 176, 136)
        # End:   #C44600 → (196, 70, 0)
        r = int(255 + t * (196 - 255))
        g = int(176 + t * (70 - 176))
        b = int(136 + t * (0 - 136))

        return f"#{r:02X}{g:02X}{b:02X}"
