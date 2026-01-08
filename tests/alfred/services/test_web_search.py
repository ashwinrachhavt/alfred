from types import SimpleNamespace

from alfred.services import web_service


class DummyConn:
    def __init__(self, *args, **kwargs):
        pass

    def search(self, q: str, **kwargs):  # type: ignore[override]
        _ = kwargs
        hit = SimpleNamespace(title="T", url="http://u", snippet="s", source="searx")
        return SimpleNamespace(provider="searx", query=q, hits=[hit], meta={"x": 1})


def test_search_web_shapes_and_tracing(monkeypatch):
    import alfred.core.dependencies as deps

    # Replace process-scoped connector provider with a dummy that returns deterministic payload.
    monkeypatch.setattr(deps, "get_primary_web_search_connector", lambda: DummyConn())
    out = web_service.search_web(
        q="hello",
        searx_k=3,
    )
    assert out["provider"] == "searx"
    assert out["query"] == "hello"
    assert out["meta"] == {"x": 1}
    assert out["hits"] == [{"title": "T", "url": "http://u", "snippet": "s", "source": "searx"}]
