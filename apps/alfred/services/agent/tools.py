"""Agent tool definitions for function calling.

Each tool is a plain dict matching OpenAI's function calling schema.
The executor maps tool names to implementation functions.

┌─────────────────────────────────────────────────┐
│  Tool Loop (max 5 iterations)                   │
│  LLM → tool_call → execute → inject result →   │
│  LLM → tool_call → execute → inject result →   │
│  LLM → final response (no tool_call)            │
└─────────────────────────────────────────────────┘
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session

from alfred.services.zettelkasten_service import ZettelkastenService

logger = logging.getLogger(__name__)

# --- Tool schemas for OpenAI function calling ---

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": "Search the knowledge base (documents and zettels) for information relevant to a query. Returns top results with titles, summaries, and relevance scores.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query. Be specific and descriptive.",
                    },
                    "domain_filter": {
                        "type": "string",
                        "description": "Optional domain/topic filter (e.g., 'philosophy', 'system-design').",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_zettel",
            "description": "Create a new zettel (atomic knowledge card) in the knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Zettel title (concise, descriptive)."},
                    "content": {"type": "string", "description": "Zettel content in markdown."},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for categorization.",
                    },
                    "topic": {"type": "string", "description": "Primary domain/topic."},
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_zettel",
            "description": "Retrieve a specific zettel by ID. Use when the user asks to see, read, or edit a particular card.",
            "parameters": {
                "type": "object",
                "properties": {
                    "zettel_id": {"type": "integer", "description": "The zettel card ID."},
                },
                "required": ["zettel_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_zettel",
            "description": "Update an existing zettel's content, tags, or topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "zettel_id": {"type": "integer", "description": "The zettel card ID to update."},
                    "title": {"type": "string", "description": "New title (optional)."},
                    "content": {"type": "string", "description": "New content in markdown (optional)."},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "New tags (optional).",
                    },
                    "topic": {"type": "string", "description": "New domain/topic (optional)."},
                },
                "required": ["zettel_id"],
            },
        },
    },
]


# --- Tool executor ---


async def execute_tool(
    tool_name: str,
    args: dict[str, Any],
    db: Session,
) -> dict[str, Any]:
    """Execute a tool by name and return the result."""
    executor = _EXECUTORS.get(tool_name)
    if not executor:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return await executor(args, db)
    except Exception as exc:
        logger.exception("Tool %s failed: %s", tool_name, exc)
        return {"error": f"Tool {tool_name} failed: {exc!s}"}


async def _search_kb(args: dict[str, Any], db: Session) -> dict[str, Any]:
    """Search documents via Qdrant and zettels via in-process cosine."""
    query = args.get("query", "")
    domain_filter = args.get("domain_filter")

    svc = ZettelkastenService(db)
    cards = svc.list_cards(q=query, topic=domain_filter, limit=10)

    results = []
    for card in cards:
        results.append({
            "zettel_id": card.id,
            "title": card.title,
            "summary": (card.summary or card.content or "")[:200],
            "topic": card.topic,
            "tags": card.tags or [],
        })

    return {"results": results, "count": len(results)}


async def _create_zettel(args: dict[str, Any], db: Session) -> dict[str, Any]:
    """Create a new zettel card."""
    svc = ZettelkastenService(db)
    card = svc.create_card(
        title=args["title"],
        content=args.get("content"),
        tags=args.get("tags"),
        topic=args.get("topic"),
    )
    db.commit()
    db.refresh(card)

    return {
        "action": "created",
        "zettel_id": card.id,
        "title": card.title,
        "summary": (card.summary or card.content or "")[:200],
        "topic": card.topic,
        "tags": card.tags or [],
    }


async def _get_zettel(args: dict[str, Any], db: Session) -> dict[str, Any]:
    """Retrieve a zettel by ID."""
    svc = ZettelkastenService(db)
    card = svc.get_card(args["zettel_id"])
    if not card:
        return {"error": f"Zettel {args['zettel_id']} not found"}

    return {
        "action": "found",
        "zettel_id": card.id,
        "title": card.title,
        "content": card.content,
        "summary": (card.summary or "")[:200],
        "topic": card.topic,
        "tags": card.tags or [],
    }


async def _update_zettel(args: dict[str, Any], db: Session) -> dict[str, Any]:
    """Update an existing zettel."""
    svc = ZettelkastenService(db)
    card = svc.get_card(args["zettel_id"])
    if not card:
        return {"error": f"Zettel {args['zettel_id']} not found"}

    fields: dict[str, Any] = {}
    if "title" in args:
        fields["title"] = args["title"]
    if "content" in args:
        fields["content"] = args["content"]
    if "tags" in args:
        fields["tags"] = args["tags"]
    if "topic" in args:
        fields["topic"] = args["topic"]

    updated = svc.update_card(card, **fields)
    db.commit()

    return {
        "action": "updated",
        "zettel_id": updated.id,
        "title": updated.title,
        "summary": (updated.summary or updated.content or "")[:200],
        "topic": updated.topic,
        "tags": updated.tags or [],
    }


_EXECUTORS = {
    "search_kb": _search_kb,
    "create_zettel": _create_zettel,
    "get_zettel": _get_zettel,
    "update_zettel": _update_zettel,
}
