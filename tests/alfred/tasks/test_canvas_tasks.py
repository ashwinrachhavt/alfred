from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_generate_diagram_task_returns_result():
    from alfred.tasks.canvas_tasks import generate_diagram_task

    mock_model = MagicMock()
    mock_model.invoke.return_value = MagicMock(content='{"elements":[],"description":"test"}')

    with (
        patch("alfred.core.llm_factory.get_chat_model", return_value=mock_model),
        patch("alfred.services.excalidraw_agent.build_diagram_prompt", return_value="prompt"),
        patch(
            "alfred.services.excalidraw_agent.parse_diagram_response",
            return_value={"elements": [], "description": "test"},
        ),
    ):
        result = generate_diagram_task(prompt="draw a box", canvas_context=None)

    assert result["elements"] == []
    assert result["description"] == "test"
    mock_model.invoke.assert_called_once_with("prompt")
