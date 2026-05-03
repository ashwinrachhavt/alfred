import json

import pytest

from alfred.connectors.web_connector import (
    SearchHit,
    SearxClient,
    WebConnector,
    _dedupe_by_url,
    _normalize_list_result,
)
from alfred.core.exceptions import ConfigurationError
from alfred.core.settings import settings


def test_normalize_list_result_various_shapes():
    items = [
        {"title": "A", "url": "http://a", "snippet": "sa"},
        {"name": "B", "link": "http://b", "content": "sb"},
        {"metadata": {"title": "C", "url": "http://c", "description": "sc"}},
    ]
    hits = _normalize_list_result(items, "searx")
    assert [h.title for h in hits] == ["A", "B", "C"]
    assert [h.url for h in hits] == ["http://a", "http://b", "http://c"]
    assert [h.snippet for h in hits] == ["sa", "sb", "sc"]

    payload = {"results": [{"title": "X", "url": "u"}]}
    hits2 = _normalize_list_result(payload, "searx")
    assert len(hits2) == 1 and hits2[0].title == "X" and hits2[0].url == "u"

    text = json.dumps([{"title": "Y", "url": "v"}])
    hits3 = _normalize_list_result(text, "searx")
    assert len(hits3) == 1 and hits3[0].title == "Y" and hits3[0].url == "v"

    # Fallback for non-JSON strings
    s = "some plain text result"
    hits4 = _normalize_list_result(s, "searx")
    assert len(hits4) == 1 and hits4[0].snippet.startswith("some plain text")


def test_dedupe_by_url():
    hits = [
        SearchHit(title="A", url="http://a", snippet=None, source="searx", raw={}),
        SearchHit(title="A2", url="HTTP://A", snippet=None, source="searx", raw={}),
        SearchHit(title="B", url=" http://b ", snippet=None, source="searx", raw={}),
        SearchHit(title="C", url=None, snippet=None, source="searx", raw={}),
    ]
    deduped = _dedupe_by_url(hits)
    urls = [h.url for h in deduped]
    assert urls == ["http://a", " http://b "]


def test_webconnector_unconfigured_without_host(monkeypatch):
    monkeypatch.delenv("SEARXNG_HOST", raising=False)
    monkeypatch.delenv("SEARX_HOST", raising=False)
    monkeypatch.setattr(settings, "searxng_host", None)
    monkeypatch.setattr(settings, "searx_host", None)
    conn = WebConnector(searx_k=3)
    resp = conn.search("hello")
    assert resp.provider == "searx"
    assert resp.hits == []
    assert resp.meta and resp.meta.get("status") == "unconfigured"


def test_webconnector_constructs_client_when_env_set(monkeypatch):
    # Construction should not hit the network; only the subsequent search would.
    monkeypatch.setattr(settings, "searxng_host", "http://127.0.0.1:8080")
    monkeypatch.setattr(settings, "searx_host", None)
    conn = WebConnector(searx_k=3)
    assert conn._client is not None


def test_searx_client_explains_json_api_forbidden(monkeypatch):
    class ForbiddenWrapper:
        def results(self, *args, **kwargs):
            raise ValueError(
                "Searx API returned an error: ",
                "<title>403 Forbidden</title>",
            )

    client = object.__new__(SearxClient)
    client._host = "http://searxng:8080"
    client._k_default = 3
    client._wrapper = ForbiddenWrapper()
    monkeypatch.setattr("alfred.connectors.web_connector.web_rate_limiter.wait", lambda _: None)

    with pytest.raises(ConfigurationError, match="JSON search API"):
        client.search("hello", num_results=3)
