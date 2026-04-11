"""Tests for the top-level Alfred graph."""
import os
from unittest.mock import patch

from alfred.agents.graph import build_alfred_graph


@patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-for-ci"})
def test_graph_builds():
    """The graph compiles without error."""
    graph = build_alfred_graph()
    assert graph is not None
