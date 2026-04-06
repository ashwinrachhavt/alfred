"""Tests for knowledge tools."""
from unittest.mock import MagicMock, patch

from alfred.agents.tools.knowledge_tools import (
    KNOWLEDGE_TOOLS,
    create_zettel,
    search_kb,
)


def test_search_kb_calls_service():
    mock_svc = MagicMock()
    mock_svc.list_cards.return_value = []
    with patch("alfred.agents.tools.knowledge_tools._get_zettel_service", return_value=mock_svc):
        result = search_kb.invoke({"query": "epistemology", "limit": 5})
    mock_svc.list_cards.assert_called_once()
    assert isinstance(result, str)  # JSON string


def test_create_zettel_calls_service():
    mock_card = MagicMock()
    mock_card.id = 42
    mock_card.title = "Test"
    mock_svc = MagicMock()
    mock_svc.create_card.return_value = mock_card
    with patch("alfred.agents.tools.knowledge_tools._get_zettel_service", return_value=mock_svc):
        result = create_zettel.invoke({"title": "Test", "content": "Body"})
    mock_svc.create_card.assert_called_once()
    assert "42" in result


def test_knowledge_tools_list_has_six_entries():
    assert len(KNOWLEDGE_TOOLS) == 6
