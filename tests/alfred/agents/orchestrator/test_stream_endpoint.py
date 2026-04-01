"""Tests for the updated /api/agent/stream endpoint."""

from __future__ import annotations

from alfred.api.agent.routes import AgentStreamRequest


def test_request_schema_has_intent_field():
    """AgentStreamRequest should accept intent and intent_args."""
    req = AgentStreamRequest(
        message="",
        intent="summarize",
        intent_args={"url": "https://example.com"},
    )
    assert req.intent == "summarize"
    assert req.intent_args == {"url": "https://example.com"}


def test_request_schema_has_max_iterations():
    """AgentStreamRequest should accept max_iterations."""
    req = AgentStreamRequest(message="hello", max_iterations=5)
    assert req.max_iterations == 5


def test_request_schema_defaults():
    """Default values for new fields should be None/10."""
    req = AgentStreamRequest(message="hello")
    assert req.intent is None
    assert req.intent_args is None
    assert req.max_iterations == 10
