"""Knowledge tools — KB search and zettel CRUD.

Each factory function takes a zettelkasten service instance and returns
a LangChain BaseTool. This allows tests to inject a fake service.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool as lc_tool

logger = logging.getLogger(__name__)


def make_search_kb_tool(zettel_service: Any):
    """Create a search_kb tool backed by the given service."""

    @lc_tool
    def search_kb(query: str, domain_filter: str = "") -> str:
        """Search the knowledge base for zettels matching a query. Returns JSON with results."""
        cards = zettel_service.list_cards(
            q=query or None,
            topic=domain_filter or None,
            limit=10,
        )
        results = [
            {
                "zettel_id": c.id,
                "title": c.title,
                "summary": (getattr(c, "summary", None) or getattr(c, "content", "") or "")[:200],
                "topic": getattr(c, "topic", ""),
                "tags": getattr(c, "tags", []) or [],
            }
            for c in cards
        ]
        return json.dumps({"results": results, "count": len(results)})

    return search_kb


def make_create_zettel_tool(zettel_service: Any):
    """Create a create_zettel tool backed by the given service."""

    @lc_tool
    def create_zettel(title: str, content: str = "", tags: list[str] = [], topic: str = "") -> str:  # noqa: B006
        """Create a new zettel (atomic knowledge card). Returns JSON with the created card."""
        from alfred.schemas.zettel import ZettelCardCreate

        data = ZettelCardCreate(
            title=title,
            content=content or None,
            tags=tags or None,
            topic=topic or None,
        )
        card = zettel_service.create_card(data)
        return json.dumps({
            "action": "created",
            "zettel_id": card.id,
            "title": card.title,
            "summary": (getattr(card, "summary", None) or getattr(card, "content", "") or "")[:200],
            "topic": getattr(card, "topic", ""),
            "tags": getattr(card, "tags", []) or [],
        })

    return create_zettel


def make_get_zettel_tool(zettel_service: Any):
    """Create a get_zettel tool backed by the given service."""

    @lc_tool
    def get_zettel(zettel_id: int) -> str:
        """Retrieve a zettel by ID. Returns JSON with the card or an error."""
        card = zettel_service.get_card(zettel_id)
        if not card:
            return json.dumps({"error": f"Zettel {zettel_id} not found"})
        return json.dumps({
            "action": "found",
            "zettel_id": card.id,
            "title": card.title,
            "content": getattr(card, "content", ""),
            "summary": (getattr(card, "summary", None) or "")[:200],
            "topic": getattr(card, "topic", ""),
            "tags": getattr(card, "tags", []) or [],
        })

    return get_zettel


def make_update_zettel_tool(zettel_service: Any):
    """Create an update_zettel tool backed by the given service."""

    @lc_tool
    def update_zettel(
        zettel_id: int,
        title: str = "",
        content: str = "",
        tags: list[str] = [],  # noqa: B006
        topic: str = "",
    ) -> str:
        """Update an existing zettel. Returns JSON with the updated card or an error."""
        from alfred.schemas.zettel import ZettelCardPatch

        card = zettel_service.get_card(zettel_id)
        if not card:
            return json.dumps({"error": f"Zettel {zettel_id} not found"})

        patch = ZettelCardPatch(
            id=zettel_id,
            title=title or None,
            content=content or None,
            tags=tags or None,
            topic=topic or None,
        )
        updated = zettel_service.update_card(zettel_id, patch)
        return json.dumps({
            "action": "updated",
            "zettel_id": updated.id,
            "title": updated.title,
            "summary": (getattr(updated, "summary", None) or getattr(updated, "content", "") or "")[:200],
            "topic": getattr(updated, "topic", ""),
            "tags": getattr(updated, "tags", []) or [],
        })

    return update_zettel
