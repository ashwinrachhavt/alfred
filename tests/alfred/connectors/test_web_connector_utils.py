import json

from alfred.connectors.web_connector import (
    SearchHit,
    WebConnector,
    _dedupe_by_url,
    _env,
    _normalize_list_result,
)


def test_env_helper(monkeypatch):
    assert _env("__NON_EXISTENT__") is None
    # Empty/whitespace returns None
    monkeypatch.setenv("SOME_EMPTY_VAR", "   ")
    assert _env("SOME_EMPTY_VAR") is None
    # Non-empty returns stripped value
    monkeypatch.setenv("SOME_VAR", "  value ")
    assert _env("SOME_VAR") == "value"


def test_normalize_list_result_various_shapes():
    items = [
        {"title": "A", "url": "http://a", "snippet": "sa"},
        {"name": "B", "link": "http://b", "content": "sb"},
        {"metadata": {"title": "C", "url": "http://c", "description": "sc"}},
    ]
    hits = _normalize_list_result(items, "ddg")
    assert [h.title for h in hits] == ["A", "B", "C"]
    assert [h.url for h in hits] == ["http://a", "http://b", "http://c"]
    assert [h.snippet for h in hits] == ["sa", "sb", "sc"]

    payload = {"results": [{"title": "X", "url": "u"}]}
    hits2 = _normalize_list_result(payload, "ddg")
    assert len(hits2) == 1 and hits2[0].title == "X" and hits2[0].url == "u"

    text = json.dumps([{"title": "Y", "url": "v"}])
    hits3 = _normalize_list_result(text, "ddg")
    assert len(hits3) == 1 and hits3[0].title == "Y" and hits3[0].url == "v"

    # Fallback for non-JSON strings
    s = "some plain text result"
    hits4 = _normalize_list_result(s, "ddg")
    assert len(hits4) == 1 and hits4[0].snippet.startswith("some plain text")


def test_dedupe_by_url():
    hits = [
        SearchHit(title="A", url="http://a", snippet=None, source="ddg", raw={}),
        SearchHit(title="A2", url="HTTP://A", snippet=None, source="ddg", raw={}),
        SearchHit(title="B", url=" http://b ", snippet=None, source="ddg", raw={}),
        SearchHit(title="C", url=None, snippet=None, source="ddg", raw={}),
    ]
    deduped = _dedupe_by_url(hits)
    urls = [h.url for h in deduped]
    assert urls == ["http://a", " http://b "]


def test_webconnector_unconfigured_provider(monkeypatch):
    # Ensure EXA is not configured; selecting mode='exa' should provide a graceful fallback
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    conn = WebConnector(mode="exa")
    resp = conn.search("hello")
    assert resp.provider == "exa"
    assert resp.hits == []
    assert resp.meta and resp.meta.get("status") == "unconfigured"
