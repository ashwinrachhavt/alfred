"""Tests for knowledge tools (search, create, get, update zettel)."""

from __future__ import annotations

from alfred.agents.orchestrator.tools.knowledge import (
    make_search_kb_tool,
    make_create_zettel_tool,
    make_get_zettel_tool,
    make_update_zettel_tool,
)


def test_search_kb_returns_results(fake_zettel_service):
    tool = make_search_kb_tool(fake_zettel_service)
    result = tool.invoke({"query": "LangGraph"})
    assert "LangGraph Basics" in result


def test_search_kb_empty_query(fake_zettel_service):
    tool = make_search_kb_tool(fake_zettel_service)
    result = tool.invoke({"query": "nonexistent xyz"})
    assert "results" in result or "[]" in result or "count" in result


def test_search_kb_with_domain_filter(fake_zettel_service):
    tool = make_search_kb_tool(fake_zettel_service)
    result = tool.invoke({"query": "", "domain_filter": "philosophy"})
    assert "Stoic" in result
    assert "LangGraph" not in result


def test_create_zettel(fake_zettel_service):
    tool = make_create_zettel_tool(fake_zettel_service)
    result = tool.invoke({"title": "New Card", "content": "Hello world", "tags": ["test"]})
    assert "New Card" in result
    assert "created" in result


def test_get_zettel_found(fake_zettel_service):
    tool = make_get_zettel_tool(fake_zettel_service)
    result = tool.invoke({"zettel_id": 1})
    assert "LangGraph Basics" in result


def test_get_zettel_not_found(fake_zettel_service):
    tool = make_get_zettel_tool(fake_zettel_service)
    result = tool.invoke({"zettel_id": 999})
    assert "not found" in result.lower()


def test_update_zettel(fake_zettel_service):
    tool = make_update_zettel_tool(fake_zettel_service)
    result = tool.invoke({"zettel_id": 1, "title": "Updated Title"})
    assert "updated" in result.lower()


def test_update_zettel_not_found(fake_zettel_service):
    tool = make_update_zettel_tool(fake_zettel_service)
    result = tool.invoke({"zettel_id": 999, "title": "Nope"})
    assert "not found" in result.lower()
