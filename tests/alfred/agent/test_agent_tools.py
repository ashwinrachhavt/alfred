from __future__ import annotations

from datetime import date
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from alfred.models.doc_storage import DocumentRow
from alfred.services.agent.tools import _search_kb
from alfred.services.zettelkasten_service import ZettelkastenService


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


@pytest.mark.asyncio
async def test_search_kb_merges_zettels_and_documents() -> None:
    session = _session()
    zettel_service = ZettelkastenService(session=session)
    zettel = zettel_service.create_card(
        title="Queue Patterns",
        content="Kafka and fan-out architectures",
        topic="system design",
        tags=["queues"],
    )

    doc_id = uuid4()
    session.add(
        DocumentRow(
            id=doc_id,
            source_url="https://example.com/queues",
            title="Queues at Scale",
            cleaned_text="Long document body about queues at scale.",
            hash="queues-at-scale",
            summary={"short": "Document summary for queue scaling."},
            tags=["queues"],
            day_bucket=date.today(),
        )
    )
    session.commit()

    doc_hits = [
        {
            "score": 0.82,
            "text": "Queue scaling chunk",
            "payload": {
                "kind": "document_chunk",
                "doc_id": str(doc_id),
                "chunk_id": f"{doc_id}:0",
                "meta": {"doc_id": str(doc_id)},
            },
        },
        {
            "score": 0.63,
            "text": "Secondary chunk",
            "payload": {
                "kind": "document_chunk",
                "doc_id": str(doc_id),
                "chunk_id": f"{doc_id}:1",
                "meta": {"doc_id": str(doc_id)},
            },
        },
    ]

    with patch(
        "alfred.services.zettelkasten_service.ZettelkastenService.semantic_search_cards",
        return_value=[(zettel, 0.95)],
    ) as mock_zettel_search, patch(
        "alfred.services.agent.tools.KnowledgeService.search",
        return_value=doc_hits,
    ) as mock_doc_search:
        result = await _search_kb({"query": "queues"}, session)

    mock_zettel_search.assert_called_once_with("queues", topic=None, limit=10)
    mock_doc_search.assert_called_once()

    assert result["count"] == 2
    assert [item["type"] for item in result["results"]] == ["zettel", "document"]

    document_result = result["results"][1]
    assert document_result["document_id"] == str(doc_id)
    assert document_result["title"] == "Queues at Scale"
    assert document_result["summary"] == "Document summary for queue scaling."


@pytest.mark.asyncio
async def test_search_kb_returns_empty_for_blank_query() -> None:
    """Empty or whitespace-only queries should return empty results, not error."""
    session = _session()

    result = await _search_kb({"query": ""}, session)
    assert result == {"results": [], "count": 0}

    result2 = await _search_kb({"query": "   "}, session)
    assert result2 == {"results": [], "count": 0}
