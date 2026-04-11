"""Knowledge agent tools -- zettel CRUD and semantic search.

Each tool is a plain function decorated with @tool (LangGraph uses the
docstring as the tool description and type annotations for the schema).
Tools return JSON strings so agents can parse results.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool

from alfred.core.database import SessionLocal
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.zettelkasten_service import ZettelkastenService

logger = logging.getLogger(__name__)


def _get_zettel_service() -> ZettelkastenService:
    """Create a ZettelkastenService with a fresh DB session."""
    session = SessionLocal()
    return ZettelkastenService(session=session)


def _get_doc_service() -> DocStorageService:
    """Create a DocStorageService with a fresh DB session."""
    session = SessionLocal()
    return DocStorageService(session=session)


@tool
def search_kb(query: str, topic: str | None = None, tags: str | None = None, limit: int = 10) -> str:
    """Search the knowledge base for zettels matching a query. Returns titles, summaries, and IDs."""
    svc = _get_zettel_service()
    cards = svc.list_cards(q=query, topic=topic, limit=limit)
    results = [
        {"id": c.id, "title": c.title, "topic": c.topic, "summary": (c.summary or c.content or "")[:200]}
        for c in cards
    ]
    return json.dumps(results)


@tool
def get_zettel(zettel_id: int) -> str:
    """Retrieve a specific zettel card by ID. Returns full content."""
    svc = _get_zettel_service()
    card = svc.get_card(zettel_id)
    if not card:
        return json.dumps({"error": f"Zettel {zettel_id} not found"})
    return json.dumps({
        "id": card.id, "title": card.title, "content": card.content,
        "tags": card.tags, "topic": card.topic, "status": card.status,
    })


@tool
def create_zettel(title: str, content: str, tags: list[str] | None = None, topic: str | None = None) -> str:
    """Create a new atomic knowledge card (zettel) in the knowledge base."""
    svc = _get_zettel_service()
    card = svc.create_card(title=title, content=content, tags=tags or [], topic=topic)
    return json.dumps({"id": card.id, "title": card.title, "status": "created"})


@tool
def update_zettel(zettel_id: int, title: str | None = None, content: str | None = None, tags: list[str] | None = None, topic: str | None = None) -> str:
    """Update an existing zettel card. Only provided fields are changed."""
    svc = _get_zettel_service()
    card = svc.get_card(zettel_id)
    if not card:
        return json.dumps({"error": f"Zettel {zettel_id} not found"})
    updates: dict[str, Any] = {}
    if title is not None:
        updates["title"] = title
    if content is not None:
        updates["content"] = content
    if tags is not None:
        updates["tags"] = tags
    if topic is not None:
        updates["topic"] = topic
    updated = svc.update_card(card, **updates)
    return json.dumps({"id": updated.id, "title": updated.title, "status": "updated"})


@tool
def get_document(doc_id: str) -> str:
    """Retrieve a source document by UUID. Returns title, summary, and content type."""
    svc = _get_doc_service()
    doc = svc.get_document_details(doc_id)
    if not doc:
        return json.dumps({"error": f"Document {doc_id} not found"})
    return json.dumps({
        "id": str(doc.get("id", doc_id)), "title": doc.get("title", ""),
        "summary": doc.get("summary", ""), "content_type": doc.get("content_type", ""),
    })


@tool
def search_documents(query: str, content_type: str | None = None, limit: int = 10) -> str:
    """Search documents in the knowledge store by query and optional content type."""
    svc = _get_doc_service()
    data = svc.list_documents(limit=limit)
    items = data.get("items", []) if isinstance(data, dict) else data
    results = [
        {"id": str(d.get("id", "")), "title": d.get("title", ""), "content_type": d.get("content_type", ""), "summary": (d.get("summary") or "")[:200]}
        for d in items
        if (not content_type or d.get("content_type") == content_type)
        and (not query or (query.lower() in (d.get("title") or "").lower()) or (query.lower() in (d.get("summary") or "").lower()))
    ][:limit]
    return json.dumps(results)


# List of all knowledge tools for agent registration
KNOWLEDGE_TOOLS = [search_kb, get_zettel, create_zettel, update_zettel, get_document, search_documents]
