"""Tests for the /api/agent/stream SSE endpoint."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool
from sqlmodel import Session, create_engine

from alfred.api.agent.routes import AgentStreamRequest
from alfred.api.agent.routes import router as agent_router
from alfred.api.dependencies import get_db_session
from alfred.models.thinking import AgentMessageRow, ThinkingSessionRow


class _FakeGraph:
    async def astream_events(
        self,
        input_state: dict,
        config: dict | None = None,
        version: str | None = None,
    ) -> AsyncIterator[dict]:
        _ = input_state, config, version
        yield {
            "event": "on_chain_stream",
            "name": "planner",
            "data": {
                "chunk": {
                    "plan": [
                        {
                            "id": "task-1",
                            "agent": "knowledge",
                            "objective": "Search Alfred's knowledge base",
                            "status": "queued",
                        }
                    ]
                }
            },
        }
        yield {
            "event": "on_chain_start",
            "name": "execute_task",
            "data": {
                "input": {
                    "current_task": {
                        "id": "task-1",
                        "agent": "knowledge",
                        "objective": "Search Alfred's knowledge base",
                    }
                }
            },
        }
        yield {
            "event": "on_chain_end",
            "name": "execute_task",
            "data": {
                "output": {
                    "task_results": [
                        {
                            "task_id": "task-1",
                            "agent": "knowledge",
                            "summary": "Found relevant LangGraph notes in Alfred.",
                        }
                    ]
                }
            },
        }
        yield {
            "event": "on_chain_end",
            "name": "writer",
            "data": {
                "output": {
                    "messages": [
                        {
                            "type": "ai",
                            "content": "Final orchestrated answer.",
                        }
                    ],
                    "final_response": "Final orchestrated answer.",
                }
            },
        }


@pytest.fixture()
def app_and_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ThinkingSessionRow.metadata.create_all(
        engine,
        tables=[ThinkingSessionRow.__table__, AgentMessageRow.__table__],
    )
    app = FastAPI()
    app.include_router(agent_router)

    def _override_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_db
    return app, TestClient(app)


def test_request_schema_has_intent_field():
    req = AgentStreamRequest(
        message="",
        intent="summarize",
        intent_args={"url": "https://example.com"},
    )
    assert req.intent == "summarize"
    assert req.intent_args == {"url": "https://example.com"}


def test_request_schema_has_max_iterations():
    req = AgentStreamRequest(message="hello", max_iterations=5)
    assert req.max_iterations == 5


def test_request_schema_defaults():
    req = AgentStreamRequest(message="hello")
    assert req.intent is None
    assert req.intent_args is None
    assert req.max_iterations == 10


def test_stream_endpoint_emits_plan_and_task_events(app_and_client, monkeypatch):
    _, client = app_and_client
    monkeypatch.setattr(
        "alfred.agents.graph.build_alfred_graph",
        lambda: _FakeGraph(),
    )

    response = client.post("/api/agent/stream", json={"message": "Find my LangGraph notes"})

    assert response.status_code == 200
    body = response.text
    assert "event: plan" in body
    assert "event: task_start" in body
    assert "event: task_done" in body
    assert "event: token" in body
    assert "Final orchestrated answer." in body
