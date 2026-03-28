from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch


def test_run_document_pipeline_calls_graph():
    """Celery task builds graph and invokes with correct state."""
    # Import at module level to avoid import-time issues
    from alfred.tasks.document_pipeline import run_document_pipeline

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "doc_id": "d1",
        "stage": "persist",
        "cache_hits": [],
        "errors": [],
    }

    mock_settings = Mock()
    mock_settings.writer_checkpoint_dsn = "postgresql://test"
    mock_settings.database_url = "postgresql+psycopg://test"

    with patch(
        "alfred.pipeline.graph.build_pipeline_graph",
        return_value=mock_graph,
    ), patch(
        "alfred.services.checkpoint_postgres.PostgresCheckpointSaver",
    ), patch(
        "alfred.services.checkpoint_postgres.PostgresCheckpointConfig",
    ), patch(
        "alfred.core.settings.settings",
        mock_settings,
    ):
        result = run_document_pipeline(doc_id="d1", user_id="u1")

    assert result["status"] == "completed"
    assert result["doc_id"] == "d1"
    mock_graph.invoke.assert_called_once()

    call_args = mock_graph.invoke.call_args
    initial_state = call_args[0][0]
    assert initial_state["doc_id"] == "d1"
    assert initial_state["force_replay"] is False
