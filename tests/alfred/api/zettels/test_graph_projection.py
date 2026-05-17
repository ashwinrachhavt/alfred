from __future__ import annotations

from typing import Any

from alfred.api.zettels.graph_projection import (
    delete_card,
    delete_edges,
    upsert_card,
    upsert_links,
)


class _FakeGraph:
    def __init__(self) -> None:
        self.deleted_cards: list[int] = []
        self.deleted_edges: list[tuple[int, int, str]] = []

    def delete_zettel(self, *, card_id: int) -> None:
        self.deleted_cards.append(card_id)

    def delete_zettel_link(self, *, from_id: int, to_id: int, type_: str) -> None:
        self.deleted_edges.append((from_id, to_id, type_))


class _FakeSync:
    def __init__(self, *, session: Any, graph: _FakeGraph) -> None:
        self.session = session
        self.graph = graph
        self.upserted_cards: list[int] = []
        self.upserted_links: list[int] = []

    def upsert_card(self, card_id: int) -> None:
        self.upserted_cards.append(card_id)

    def upsert_link(self, link_id: int) -> None:
        self.upserted_links.append(link_id)


def test_upsert_card_noops_without_card_id() -> None:
    assert upsert_card(None, object(), graph_service_factory=lambda: _FakeGraph()) is False


def test_upsert_card_projects_with_injected_sync_factory() -> None:
    graph = _FakeGraph()
    syncs: list[_FakeSync] = []

    def sync_factory(**kwargs: Any) -> _FakeSync:
        sync = _FakeSync(**kwargs)
        syncs.append(sync)
        return sync

    assert (
        upsert_card(
            42,
            object(),
            graph_service_factory=lambda: graph,
            sync_factory=sync_factory,
        )
        is True
    )
    assert syncs[0].upserted_cards == [42]


def test_upsert_links_projects_each_link_id() -> None:
    graph = _FakeGraph()
    syncs: list[_FakeSync] = []

    def sync_factory(**kwargs: Any) -> _FakeSync:
        sync = _FakeSync(**kwargs)
        syncs.append(sync)
        return sync

    assert (
        upsert_links(
            [1, 2],
            object(),
            graph_service_factory=lambda: graph,
            sync_factory=sync_factory,
        )
        is True
    )
    assert syncs[0].upserted_links == [1, 2]


def test_delete_card_uses_graph_service() -> None:
    graph = _FakeGraph()

    assert delete_card(7, graph_service_factory=lambda: graph) is True

    assert graph.deleted_cards == [7]


def test_delete_edges_deletes_all_pairs() -> None:
    graph = _FakeGraph()

    assert (
        delete_edges(
            [(1, 2, "reference"), (2, 3, "extends")],
            graph_service_factory=lambda: graph,
        )
        is True
    )
    assert graph.deleted_edges == [(1, 2, "reference"), (2, 3, "extends")]
