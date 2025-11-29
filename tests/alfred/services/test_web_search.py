from types import SimpleNamespace

from alfred.services import web_search


class DummyConn:
    def __init__(self, *args, **kwargs):
        pass

    def search(self, q: str):
        hit = SimpleNamespace(title="T", url="http://u", snippet="s", source="ddg")
        return SimpleNamespace(provider="ddg", query=q, hits=[hit], meta={"x": 1})


def test_search_web_shapes_and_tracing(monkeypatch):
    # Replace WebConnector with a dummy that returns deterministic payload
    monkeypatch.setattr(web_search, "WebConnector", DummyConn)
    out = web_search.search_web(
        q="hello",
        mode="auto",
        brave_pages=2,
        ddg_max_results=5,
        exa_num_results=3,
        tavily_max_results=4,
        tavily_topic="general",
        you_num_results=2,
        searx_k=3,
    )
    assert out["provider"] == "ddg"
    assert out["query"] == "hello"
    assert out["meta"] == {"x": 1}
    assert out["hits"] == [{"title": "T", "url": "http://u", "snippet": "s", "source": "ddg"}]
