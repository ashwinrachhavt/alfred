from pathlib import Path

from alfred.core import agno_tracing


def test_agno_tracing_disabled_without_uri(monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    assert agno_tracing.init() is False
    assert agno_tracing.is_enabled() is False


def test_agno_tracing_file_store_agent_run(tmp_path, monkeypatch):
    uri = f"file://{tmp_path.as_posix()}"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "test-agno")

    ok = agno_tracing.init()
    assert ok is True
    assert agno_tracing.is_enabled() is True

    with agno_tracing.agent_run("TestAgent", {"x": 1}):
        agno_tracing.log_tool_call("dummy_tool", {"a": 1}, result={"b": 2})
        agno_tracing.log_knowledge_event("search", {"q": "hi", "n": 1})
        agno_tracing.log_output({"y": 3})

    # Ensure the path is created
    assert Path(tmp_path).exists()
