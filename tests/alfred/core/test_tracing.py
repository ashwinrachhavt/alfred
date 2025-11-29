from alfred.core import tracing
from alfred.core.config import settings


def _reset_tracing_state(monkeypatch):
    monkeypatch.setattr(tracing, "_client_cache", None, raising=False)
    monkeypatch.setattr(tracing, "_observe_impl", None, raising=False)


def test_tracing_noop_without_keys(monkeypatch):
    # Ensure tracing is enabled but keys are missing
    monkeypatch.setattr(settings, "langfuse_tracing_enabled", True, raising=False)
    monkeypatch.setattr(settings, "langfuse_public_key", None, raising=False)
    monkeypatch.setattr(settings, "langfuse_secret_key", None, raising=False)
    _reset_tracing_state(monkeypatch)

    assert tracing.lf_get_client() is None

    # No-op decorator returns the original function unchanged
    def f(x):
        return x + 1

    wrapped = tracing.lf_observe(name="t")(f)
    assert wrapped is f
    assert wrapped(2) == 3

    # Update functions should not raise
    tracing.lf_update_span(input={"a": 1})
    tracing.lf_update_trace(name="n", tags=["t1"]).__class__
