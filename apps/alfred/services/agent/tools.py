"""Agent tool definitions for function calling.

Unified tool registry: hand-written core tools + auto-adapted LangChain tools.
All tools are available to the flat agent loop as OpenAI function calling schemas.

┌─────────────────────────────────────────────────┐
│  Tool Loop (max 10 iterations)                  │
│  LLM → tool_call → execute → inject result →   │
│  LLM → tool_call → execute → inject result →   │
│  LLM → final response (no tool_call)            │
└─────────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import BaseTool
from sqlmodel import Session

from alfred.services.zettelkasten_service import ZettelkastenService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LangChain → OpenAI schema adapter
# ---------------------------------------------------------------------------

def _langchain_tool_to_openai_schema(tool: BaseTool) -> dict[str, Any]:
    """Convert a LangChain BaseTool to an OpenAI function calling schema."""
    # LangChain tools expose args_schema as a Pydantic model
    schema = tool.get_input_schema().model_json_schema()

    # Clean up the schema for OpenAI compatibility
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # Remove Pydantic internal fields
    clean_props = {}
    for name, prop in properties.items():
        clean_prop = {k: v for k, v in prop.items() if k in ("type", "description", "default", "items", "enum")}
        if "anyOf" in prop:
            # Handle Optional types: pick the non-null type
            for variant in prop["anyOf"]:
                if variant.get("type") != "null":
                    clean_prop["type"] = variant.get("type", "string")
                    if "description" not in clean_prop and "description" in variant:
                        clean_prop["description"] = variant["description"]
                    break
        if "type" not in clean_prop:
            clean_prop["type"] = "string"
        clean_props[name] = clean_prop

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": {
                "type": "object",
                "properties": clean_props,
                "required": required,
            },
        },
    }


async def _execute_langchain_tool(tool: BaseTool, args: dict[str, Any]) -> dict[str, Any]:
    """Execute a LangChain tool and return the result as a dict."""
    try:
        # LangChain tools can be sync or async
        if hasattr(tool, "ainvoke"):
            result = await tool.ainvoke(args)
        else:
            result = tool.invoke(args)

        # Tools return JSON strings — parse them
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return {"result": result}
        return result if isinstance(result, dict) else {"result": str(result)}
    except Exception as exc:
        logger.exception("LangChain tool %s failed: %s", tool.name, exc)
        return {"error": f"Tool {tool.name} failed: {exc!s}"}


# ---------------------------------------------------------------------------
# Core hand-written tools (OpenAI schema + executor)
# These 4 tools use the passed DB session directly — no session leaks.
# ---------------------------------------------------------------------------

CORE_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": (
                "Search the knowledge base for zettels (atomic knowledge cards) matching a query. "
                "Use this FIRST when the user asks about their knowledge, before answering from memory. "
                "Returns titles, summaries, topics, and IDs."
            ),
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
            "description": (
                "Create a new zettel (atomic knowledge card) in the knowledge base. "
                "Use when the user asks to save, capture, or remember something, or when you "
                "synthesize insights worth preserving. Always give cards a clear title and tags."
            ),
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
            "description": (
                "Retrieve a specific zettel by ID to read its full content. "
                "Use when a search result looks relevant and you need the complete text, "
                "or when the user references a specific card."
            ),
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
            "description": (
                "Update an existing zettel's content, title, tags, or topic. "
                "Use when the user asks to edit, refine, or correct a card."
            ),
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
    {
        "type": "function",
        "function": {
            "name": "list_recent_cards",
            "description": (
                "List the most recent zettel cards in the knowledge base. "
                "Use for browsing, overviews, and open-ended questions like "
                "'What did I learn recently?' or 'Show me my latest cards'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of cards to return (default 20).",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional topic filter.",
                    },
                },
                "required": [],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Core tool executors
# ---------------------------------------------------------------------------


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


async def _list_recent_cards(args: dict[str, Any], db: Session) -> dict[str, Any]:
    """List recent zettel cards."""
    svc = ZettelkastenService(db)
    limit = args.get("limit", 20)
    topic = args.get("topic")
    cards = svc.list_cards(limit=limit, topic=topic)

    results = []
    for card in cards:
        results.append({
            "zettel_id": card.id,
            "title": card.title,
            "summary": (card.summary or card.content or "")[:150],
            "topic": card.topic,
            "tags": card.tags or [],
        })
    return {"results": results, "count": len(results)}


_CORE_EXECUTORS: dict[str, Any] = {
    "search_kb": _search_kb,
    "create_zettel": _create_zettel,
    "get_zettel": _get_zettel,
    "update_zettel": _update_zettel,
    "list_recent_cards": _list_recent_cards,
}


# ---------------------------------------------------------------------------
# Unified tool registry: core + LangChain tools
# ---------------------------------------------------------------------------

# Cache for adapted LangChain tools
_lc_tools_cache: dict[str, BaseTool] = {}
_lc_schemas_cache: list[dict[str, Any]] = []
_initialized = False


def _load_langchain_tools() -> None:
    """Import and register all LangChain tools from agents/tools/."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    try:
        from alfred.agents.tools.connection_tools import CONNECTION_TOOLS
        from alfred.agents.tools.connector_tools import CONNECTOR_TOOLS
        from alfred.agents.tools.enrichment_tools import ENRICHMENT_TOOLS
        from alfred.agents.tools.import_tools import IMPORT_TOOLS
        from alfred.agents.tools.knowledge_tools import KNOWLEDGE_TOOLS
        from alfred.agents.tools.learning_tools import LEARNING_TOOLS
        from alfred.agents.tools.research_tools import RESEARCH_TOOLS
        from alfred.agents.tools.writing_tools import WRITING_TOOLS

        all_tools: list[BaseTool] = [
            *KNOWLEDGE_TOOLS,
            *CONNECTION_TOOLS,
            *LEARNING_TOOLS,
            *CONNECTOR_TOOLS,
            *ENRICHMENT_TOOLS,
            *IMPORT_TOOLS,
            *RESEARCH_TOOLS,
            *WRITING_TOOLS,
        ]

        for tool in all_tools:
            # Skip tools that overlap with core hand-written tools
            if tool.name in _CORE_EXECUTORS:
                logger.debug("Skipping LangChain tool %s (core tool exists)", tool.name)
                continue
            _lc_tools_cache[tool.name] = tool
            _lc_schemas_cache.append(_langchain_tool_to_openai_schema(tool))

        logger.info(
            "Loaded %d LangChain tools (+ %d core tools = %d total)",
            len(_lc_tools_cache),
            len(_CORE_EXECUTORS),
            len(_lc_tools_cache) + len(_CORE_EXECUTORS),
        )
    except Exception:
        logger.exception("Failed to load LangChain tools — agent will have core tools only")


def get_all_tool_schemas() -> list[dict[str, Any]]:
    """Return all tool schemas (core + LangChain) for OpenAI function calling."""
    _load_langchain_tools()
    return CORE_TOOL_SCHEMAS + _lc_schemas_cache


async def execute_tool(
    tool_name: str,
    args: dict[str, Any],
    db: Session,
) -> dict[str, Any]:
    """Execute a tool by name and return the result.

    Core tools use the passed DB session directly.
    LangChain tools manage their own sessions internally.
    """
    # Try core tools first (use passed DB session)
    core_executor = _CORE_EXECUTORS.get(tool_name)
    if core_executor:
        try:
            return await core_executor(args, db)
        except Exception as exc:
            logger.exception("Core tool %s failed: %s", tool_name, exc)
            return {"error": f"Tool {tool_name} failed: {exc!s}"}

    # Try LangChain tools (they manage their own sessions)
    _load_langchain_tools()
    lc_tool = _lc_tools_cache.get(tool_name)
    if lc_tool:
        return await _execute_langchain_tool(lc_tool, args)

    return {"error": f"Unknown tool: {tool_name}"}


# Legacy compatibility aliases
TOOL_SCHEMAS = CORE_TOOL_SCHEMAS  # old code references this
