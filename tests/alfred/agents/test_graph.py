"""Tests for the top-level Alfred graph."""
from alfred.agents.graph import build_alfred_graph


def test_graph_builds():
    """The graph compiles without error."""
    graph = build_alfred_graph()
    assert graph is not None
