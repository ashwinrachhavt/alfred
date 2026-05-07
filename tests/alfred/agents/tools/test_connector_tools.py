from __future__ import annotations

import json
from types import SimpleNamespace

from alfred.agents.tools import connector_tools


def test_query_web_uses_web_connector_response_shape(monkeypatch):
    class DummyWebConnector:
        def __init__(self, *, searx_k: int = 10):
            self.searx_k = searx_k

        def search(self, query: str, *, num_results: int | None = None, **_kwargs):
            assert query == "polymath tools"
            assert num_results == 2
            return SimpleNamespace(
                hits=[
                    SimpleNamespace(
                        title="Official page",
                        url="https://example.com",
                        snippet="Source-backed result",
                        source="searx",
                    )
                ]
            )

    monkeypatch.setattr("alfred.connectors.web_connector.WebConnector", DummyWebConnector)

    payload = connector_tools.query_web.invoke({"query": "polymath tools", "max_results": 2})
    assert json.loads(payload) == [
        {
            "title": "Official page",
            "url": "https://example.com",
            "snippet": "Source-backed result",
            "source": "searx",
        }
    ]


def test_query_semantic_scholar_uses_client_method(monkeypatch):
    class DummySemanticScholarClient:
        def search_by_keyword(self, *, keyword: str, limit: int):
            assert keyword == "argument mapping"
            assert limit == 1
            return [
                {
                    "title": "Argument mapping paper",
                    "authors": [{"name": "A. Researcher"}],
                    "abstract": "A" * 500,
                    "year": 2025,
                    "citationCount": 42,
                    "paperId": "paper-1",
                }
            ]

    monkeypatch.setattr(
        "alfred.connectors.semantic_scholar_connector.SemanticScholarClient",
        DummySemanticScholarClient,
    )

    payload = connector_tools.query_semantic_scholar.invoke(
        {"query": "argument mapping", "limit": 1}
    )
    assert json.loads(payload) == [
        {
            "title": "Argument mapping paper",
            "authors": ["A. Researcher"],
            "abstract": "A" * 300,
            "year": 2025,
            "citation_count": 42,
            "paper_id": "paper-1",
        }
    ]
