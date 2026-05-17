from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from alfred.models.zettel import ZettelCard
from alfred.services.agent.tools import CORE_TOOL_SCHEMAS, _search_kb


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _card(session: Session, **overrides) -> ZettelCard:
    data = {
        "title": "Default card",
        "content": "Default body",
        "summary": "Default summary",
        "topic": "default",
        "tags": [],
        "status": "active",
    }
    data.update(overrides)
    card = ZettelCard(**data)
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


@pytest.mark.asyncio
async def test_search_kb_finds_zettels_by_tag_metadata() -> None:
    session = _session()
    card = _card(
        session,
        title="Supervisor had two consumers, not one (LoanOS lesson)",
        content="The supervisor was also acting as a dispatcher for chat.",
        topic="agentic-architecture",
        tags=["agentic", "supervisor", "loanos", "lesson", "registry-coupling"],
    )

    result = await _search_kb(
        {"query": "loanos", "tags": ["loanos"], "search_mode": "metadata"},
        session,
    )

    assert result["count"] == 1
    assert result["results"][0]["zettel_id"] == card.id
    assert result["results"][0]["type"] == "zettel"
    assert "tag:loanos" in result["results"][0]["match_reason"]


@pytest.mark.asyncio
async def test_search_kb_parses_tag_list_queries() -> None:
    session = _session()
    card = _card(
        session,
        title="Supervisor had two consumers, not one (LoanOS lesson)",
        topic="agentic-architecture",
        tags=["agentic", "supervisor", "loanos", "lesson", "registry-coupling"],
    )

    result = await _search_kb(
        {"query": "Tags agentic supervisor loanos lesson registry-coupling"},
        session,
    )

    assert result["count"] == 1
    assert result["results"][0]["zettel_id"] == card.id
    assert result["results"][0]["score"] > 0


@pytest.mark.asyncio
async def test_search_kb_matches_hyphen_space_and_compact_variants() -> None:
    session = _session()
    card = _card(
        session,
        title="Registry coupling in agent dispatch",
        tags=["registry-coupling"],
    )

    result = await _search_kb({"query": "registry coupling"}, session)

    assert result["count"] == 1
    assert result["results"][0]["zettel_id"] == card.id


def test_search_kb_schema_supports_metadata_only_calls() -> None:
    schema = next(item for item in CORE_TOOL_SCHEMAS if item["function"]["name"] == "search_kb")
    parameters = schema["function"]["parameters"]

    assert parameters["required"] == []
    assert "tags" in parameters["properties"]
    assert parameters["properties"]["search_mode"]["enum"] == ["broad", "metadata"]


@pytest.mark.asyncio
async def test_search_kb_returns_empty_for_blank_query() -> None:
    """Empty or whitespace-only queries should return empty results, not error."""
    session = _session()

    result = await _search_kb({"query": ""}, session)
    assert result == {"results": [], "count": 0}

    result2 = await _search_kb({"query": "   "}, session)
    assert result2 == {"results": [], "count": 0}
