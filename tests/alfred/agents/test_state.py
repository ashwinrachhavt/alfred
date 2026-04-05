"""Tests for agent state schema."""
from alfred.agents.state import AlfredState, IngestTeamState, KnowledgeTeamState, SynthesisTeamState


def test_alfred_state_has_required_keys():
    """AlfredState TypedDict has all required keys."""
    keys = AlfredState.__annotations__
    assert "messages" in keys
    assert "user_id" in keys
    assert "intent" in keys
    assert "phase" in keys
    assert "knowledge_results" in keys
    assert "research_results" in keys
    assert "connector_results" in keys
    assert "enrichment_results" in keys
    assert "final_response" in keys
    assert "artifacts" in keys


def test_team_states_have_messages():
    """All team states include messages."""
    for state_cls in (IngestTeamState, KnowledgeTeamState, SynthesisTeamState):
        assert "messages" in state_cls.__annotations__, f"{state_cls.__name__} missing messages"
