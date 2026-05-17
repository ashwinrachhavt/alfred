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
import re
from typing import Any

from langchain_core.tools import BaseTool
from sqlmodel import Session

from alfred.core.settings import settings
from alfred.services.notes_filesystem_service import (
    FilesystemPathNotAllowedError,
    FilesystemPathNotFoundError,
    NotesFilesystemService,
)
from alfred.services.notes_service import NoteNotFoundError, NotesService, WorkspaceNotFoundError
from alfred.services.zettelkasten_service import ZettelkastenService

logger = logging.getLogger(__name__)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


# ---------------------------------------------------------------------------
# LangChain → OpenAI schema adapter
# ---------------------------------------------------------------------------


def _clean_property(prop: dict[str, Any]) -> dict[str, Any]:
    """Clean a single JSON schema property for OpenAI compatibility.

    Handles: Optional types (anyOf with null), arrays without items,
    nested objects, and Pydantic-specific fields.
    """
    clean: dict[str, Any] = {}

    # Handle Optional types: anyOf with null variant
    if "anyOf" in prop:
        for variant in prop["anyOf"]:
            if variant.get("type") == "null":
                continue
            # Found the non-null type — use it as the base
            clean["type"] = variant.get("type", "string")
            if "description" in variant:
                clean["description"] = variant["description"]
            if "items" in variant:
                clean["items"] = _clean_property(variant["items"])
            if "enum" in variant:
                clean["enum"] = variant["enum"]
            break
    else:
        if "type" in prop:
            clean["type"] = prop["type"]

    # Carry over standard fields
    for field in ("description", "default", "enum"):
        if field in prop and field not in clean:
            clean[field] = prop[field]

    # Handle arrays: MUST have items or OpenAI rejects the schema
    if clean.get("type") == "array":
        if "items" in prop:
            clean["items"] = _clean_property(prop["items"])
        elif "items" not in clean:
            # Fallback: untyped array → array of strings
            clean["items"] = {"type": "string"}

    # Default to string if no type resolved
    if "type" not in clean:
        clean["type"] = "string"

    return clean


def _langchain_tool_to_openai_schema(tool: BaseTool) -> dict[str, Any]:
    """Convert a LangChain BaseTool to an OpenAI function calling schema."""
    schema = tool.get_input_schema().model_json_schema()

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    clean_props = {}
    for name, prop in properties.items():
        clean_props[name] = _clean_property(prop)

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
                "Search the knowledge base for zettels (atomic knowledge cards) matching text, "
                "topics, or tags. This search is metadata-aware and tries forgiving variants "
                "such as camel-case splits, hyphen/space variants, and compact spellings. "
                "Use this FIRST when the user asks about their knowledge, before answering from memory. "
                "Returns titles, summaries, topics, tags, IDs, match reasons, and scores."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Optional when tags or topic filters are provided. Use the user's wording "
                            "first; if no results, retry with likely aliases, acronyms, tag spellings, "
                            "and hyphen/space variants."
                        ),
                    },
                    "domain_filter": {
                        "type": "string",
                        "description": (
                            "Optional domain/topic filter (e.g., 'philosophy', 'system-design'). "
                            "Prefer topic when the user names a topic or domain."
                        ),
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional tags to search. Use this when the user says tagged, tags, "
                            "labels, or gives a tag list."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of zettels to return. Defaults to 10; max 50.",
                    },
                    "search_mode": {
                        "type": "string",
                        "enum": ["broad", "metadata"],
                        "description": (
                            "Use broad for normal retrieval. Use metadata when the user specifically "
                            "asks for tags/topics and body-text matches would be distracting."
                        ),
                    },
                },
                "required": [],
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
                    "title": {
                        "type": "string",
                        "description": "Zettel title (concise, descriptive).",
                    },
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
                    "zettel_id": {
                        "type": "integer",
                        "description": "The zettel card ID to update.",
                    },
                    "title": {"type": "string", "description": "New title (optional)."},
                    "content": {
                        "type": "string",
                        "description": "New content in markdown (optional).",
                    },
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
    {
        "type": "function",
        "function": {
            "name": "import_notes_from_filesystem",
            "description": (
                "Import a server-visible local file or folder into Alfred Notes. "
                "Use when the user asks to import notes, a folder, an export, or local "
                "text files into Notes. The path must exist on the backend machine and "
                "must be within the allowed filesystem roots. If workspace_id is "
                "omitted, imports into the default Personal workspace."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path, ~/ path, or home-relative path to import.",
                    },
                    "workspace_id": {
                        "type": "string",
                        "description": "Optional Notes workspace UUID. Defaults to Personal.",
                    },
                    "parent_id": {
                        "type": "string",
                        "description": "Optional parent note UUID to import under.",
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "Maximum notes to create, between 1 and 500. Default 200.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_note",
            "description": (
                "Create a new note in Alfred Notes (a Notion-style page). "
                "Use when the user asks to draft, compose, or save freeform writing. "
                "Wiki-links of the form [[card title]] in content_markdown are "
                "auto-resolved and persisted as edges to existing zettels."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Note title.",
                    },
                    "content_markdown": {
                        "type": "string",
                        "description": "Markdown body. May include [[wiki links]].",
                    },
                    "workspace_id": {
                        "type": "string",
                        "description": "Optional workspace UUID. Defaults to Personal.",
                    },
                    "parent_id": {
                        "type": "string",
                        "description": "Optional parent note UUID for nesting.",
                    },
                    "icon": {
                        "type": "string",
                        "description": "Optional emoji icon.",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_note",
            "description": (
                "Edit an existing note's title, content, or icon. Wiki-links in "
                "the new content_markdown are re-resolved and synced (links to "
                "removed targets are dropped, new ones inserted)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "string",
                        "description": "Note UUID to update.",
                    },
                    "title": {"type": "string"},
                    "content_markdown": {"type": "string"},
                    "icon": {"type": "string"},
                },
                "required": ["note_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search_searxng",
            "description": (
                "Search the web using SearXNG metasearch engine (local infrastructure). "
                "Returns results from multiple search engines. Use for current events, "
                "facts, definitions, or any question that benefits from web data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return (default 5).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "firecrawl_search",
            "description": (
                "Search the web using Firecrawl (local infrastructure). Returns content-rich "
                "results with full page text. Best for finding detailed articles and content. "
                "Use when you need more than snippets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 3).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "firecrawl_scrape",
            "description": (
                "Scrape a specific URL using Firecrawl (local infrastructure). Returns the "
                "full page content as markdown. Use when you have a URL and need its content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to scrape.",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_task",
            "description": (
                "Delegate a complex task to a specialist sub-agent that runs in its own "
                "context window. The sub-agent has focused tools and expertise. Use this when: "
                "(1) a task requires deep focus on a single domain (research, writing, learning), "
                "(2) the task is complex enough that you'd need multiple sequential tool calls, "
                "(3) you want to keep the main conversation clean while a specialist works. "
                "Available specialists: knowledge (KB search/CRUD), research (web/papers), "
                "writing (drafts/summaries/synthesis), learning (quizzes/reviews/assessment), "
                "connection (find links between ideas), connector (Notion/GitHub/RSS imports)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": (
                            "Clear description of what the sub-agent should do. "
                            "Be specific about the objective and expected output."
                        ),
                    },
                    "agent_type": {
                        "type": "string",
                        "description": (
                            "Which specialist to use: knowledge, research, writing, "
                            "learning, connection, or connector."
                        ),
                        "enum": [
                            "knowledge",
                            "research",
                            "writing",
                            "learning",
                            "connection",
                            "connector",
                        ],
                    },
                    "context": {
                        "type": "string",
                        "description": (
                            "Optional context to pass to the sub-agent. "
                            "Include relevant information from the conversation."
                        ),
                    },
                },
                "required": ["task", "agent_type"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Core tool executors
# ---------------------------------------------------------------------------


async def _search_kb(args: dict[str, Any], db: Session) -> dict[str, Any]:
    """Search zettels with text, topic, and tag-aware matching."""
    query = str(args.get("query") or "").strip()
    domain_filter = args.get("domain_filter") or args.get("topic")
    tags = args.get("tags") or args.get("tag_filter")
    search_mode = str(args.get("search_mode") or "broad").strip().lower()
    if search_mode not in {"broad", "metadata"}:
        search_mode = "broad"

    try:
        limit = int(args.get("limit") or 10)
    except (TypeError, ValueError):
        limit = 10

    svc = ZettelkastenService(db)
    matches = svc.search_cards(
        query=query,
        topic=domain_filter,
        tags=tags,
        limit=limit,
        search_mode=search_mode,
    )

    results = []
    for match in matches:
        card = match.card
        results.append(
            {
                "type": "zettel",
                "zettel_id": card.id,
                "title": card.title,
                "summary": (card.summary or card.content or "")[:200],
                "topic": card.topic,
                "tags": card.tags or [],
                "score": round(match.score, 2),
                "match_reason": match.reasons,
            }
        )

    if not query and not domain_filter and not tags:
        return {"results": [], "count": 0}

    return {
        "results": results,
        "count": len(results),
        "filters": {
            "query": query,
            "topic": domain_filter,
            "tags": tags or [],
            "search_mode": search_mode,
            "limit": limit,
        },
    }


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
        results.append(
            {
                "zettel_id": card.id,
                "title": card.title,
                "summary": (card.summary or card.content or "")[:150],
                "topic": card.topic,
                "tags": card.tags or [],
            }
        )
    return {"results": results, "count": len(results)}


async def _import_notes_from_filesystem(args: dict[str, Any], db: Session) -> dict[str, Any]:
    """Import server-visible text files into Alfred Notes."""
    path = str(args.get("path") or "").strip()
    if not path:
        return {"error": "path is required"}

    parent_id = args.get("parent_id") or None
    workspace_id = args.get("workspace_id") or None

    try:
        max_files = int(args.get("max_files", 200) or 200)
    except (TypeError, ValueError):
        return {"error": "max_files must be an integer"}

    notes = NotesService(db)

    try:
        if workspace_id:
            workspace = notes.get_workspace(workspace_id)
        elif parent_id:
            parent = notes.get_note(parent_id)
            workspace = notes.get_workspace(parent.workspace_id)
            workspace_id = str(workspace.id)
        else:
            workspace = notes.get_or_create_default_workspace(user_id=None)
            workspace_id = str(workspace.id)

        result = NotesFilesystemService(db).import_path(
            workspace_id=workspace_id,
            path=path,
            parent_id=parent_id,
            user_id=None,
            max_files=max_files,
        )
    except (
        FilesystemPathNotAllowedError,
        FilesystemPathNotFoundError,
        WorkspaceNotFoundError,
        NoteNotFoundError,
        ValueError,
    ) as exc:
        return {"error": str(exc)}

    return {
        "action": "imported_notes",
        "workspace_id": str(workspace.id),
        "workspace_name": workspace.name,
        "source_path": result.source_path,
        "root_note_id": result.root_note_id,
        "imported_count": result.imported_count,
        "skipped_count": result.skipped_count,
        "skipped_paths": result.skipped_paths,
    }


_WIKI_LINK_RE = re.compile(r"\[\[([^\[\]\|\n]{1,200})(?:\|[^\[\]\n]*)?\]\]")


def _extract_wiki_link_titles(markdown: str | None) -> list[str]:
    if not markdown:
        return []
    seen: set[str] = set()
    titles: list[str] = []
    for match in _WIKI_LINK_RE.finditer(markdown):
        title = (match.group(1) or "").strip()
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        titles.append(title)
    return titles


def _sync_note_wiki_links(
    db: Session, *, note_id: str, content_markdown: str | None
) -> int:
    """Resolve [[X]] tokens and persist wiki_links rows. Returns count synced."""
    titles = _extract_wiki_link_titles(content_markdown)
    zk = ZettelkastenService(db)
    target_ids = zk.resolve_wiki_link_titles(titles) if titles else []
    zk.sync_wiki_links(
        source_type="note",
        source_id=note_id,
        target_card_ids=target_ids,
    )
    return len(target_ids)


async def _create_note(args: dict[str, Any], db: Session) -> dict[str, Any]:
    title = (args.get("title") or "").strip()
    if not title:
        return {"error": "title is required"}

    content_markdown = args.get("content_markdown") or ""
    workspace_id = args.get("workspace_id") or None
    parent_id = args.get("parent_id") or None
    icon = args.get("icon") or None

    notes = NotesService(db)
    try:
        row = notes.create_note(
            workspace_id=workspace_id,
            parent_id=parent_id,
            title=title,
            icon=icon,
            content_markdown=content_markdown,
        )
    except (WorkspaceNotFoundError, NoteNotFoundError, ValueError) as exc:
        return {"error": str(exc)}

    try:
        wiki_link_count = _sync_note_wiki_links(
            db, note_id=str(row.id), content_markdown=content_markdown
        )
    except Exception:
        logger.exception("create_note: wiki-link sync failed for %s", row.id)
        wiki_link_count = 0

    return {
        "action": "created",
        "note_id": str(row.id),
        "title": row.title,
        "workspace_id": str(row.workspace_id),
        "wiki_link_count": wiki_link_count,
    }


async def _update_note(args: dict[str, Any], db: Session) -> dict[str, Any]:
    note_id = args.get("note_id")
    if not note_id:
        return {"error": "note_id is required"}

    notes = NotesService(db)
    fields: dict[str, Any] = {}
    if "title" in args and args["title"] is not None:
        fields["title"] = args["title"]
    if "content_markdown" in args and args["content_markdown"] is not None:
        fields["content_markdown"] = args["content_markdown"]
    if "icon" in args and args["icon"] is not None:
        fields["icon"] = args["icon"]

    try:
        row = notes.update_note(note_id, **fields)
    except NoteNotFoundError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}

    # Re-sync wiki-links from the *updated* content. If content_markdown was
    # not in the patch, fall back to the row's current value so we never
    # silently desync the edge set.
    content_for_sync = fields.get("content_markdown", row.content_markdown)
    try:
        wiki_link_count = _sync_note_wiki_links(
            db, note_id=str(row.id), content_markdown=content_for_sync
        )
    except Exception:
        logger.exception("update_note: wiki-link sync failed for %s", row.id)
        wiki_link_count = 0

    return {
        "action": "updated",
        "note_id": str(row.id),
        "title": row.title,
        "wiki_link_count": wiki_link_count,
    }


async def _web_search_searxng(args: dict[str, Any], db: Session) -> dict[str, Any]:
    """Search the web using local SearXNG metasearch."""
    import httpx

    query = args.get("query", "")
    max_results = args.get("max_results", 5)
    searxng_host = settings.searxng_host or settings.searx_host
    if not searxng_host:
        return {"error": "SearXNG is not configured. Set SEARXNG_HOST or SEARX_HOST."}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                _join_url(searxng_host, "/search"),
                params={"q": query, "format": "json"},
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for r in data.get("results", [])[:max_results]:
            results.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:300],
                }
            )
        return {"results": results, "count": len(results), "source": "searxng"}
    except Exception as exc:
        return {"error": f"SearXNG search failed: {exc!s}"}


async def _firecrawl_search(args: dict[str, Any], db: Session) -> dict[str, Any]:
    """Search the web using local Firecrawl."""
    import httpx

    query = args.get("query", "")
    limit = args.get("limit", 3)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _join_url(settings.firecrawl_base_url, "/search"),
                json={"query": query, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for r in data.get("data", []):
            results.append(
                {
                    "title": r.get("title", "") or r.get("metadata", {}).get("title", ""),
                    "url": r.get("url", ""),
                    "content": (r.get("markdown", "") or r.get("content", ""))[:500],
                }
            )
        return {"results": results, "count": len(results), "source": "firecrawl"}
    except Exception as exc:
        return {"error": f"Firecrawl search failed: {exc!s}"}


async def _firecrawl_scrape(args: dict[str, Any], db: Session) -> dict[str, Any]:
    """Scrape a URL using local Firecrawl."""
    import httpx

    url = args.get("url", "")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _join_url(settings.firecrawl_base_url, "/scrape"),
                json={"url": url, "formats": ["markdown"]},
            )
            resp.raise_for_status()
            data = resp.json()

        content = data.get("data", {}).get("markdown", "")
        metadata = data.get("data", {}).get("metadata", {})
        return {
            "title": metadata.get("title", ""),
            "url": url,
            "content": content[:3000],  # Cap to avoid token overflow
            "source": "firecrawl",
        }
    except Exception as exc:
        return {"error": f"Firecrawl scrape failed: {exc!s}"}


async def _delegate_task(args: dict[str, Any], db: Session) -> dict[str, Any]:
    """Spawn a sub-agent with its own context window to handle a complex task."""
    from alfred.services.agent.agent_types import AGENT_TYPES
    from alfred.services.agent.subagent import SubAgentRunner

    task = args.get("task", "")
    agent_type = args.get("agent_type", "")
    context = args.get("context")

    if not task:
        return {"error": "Task description is required."}
    if agent_type not in AGENT_TYPES:
        return {
            "error": f"Unknown agent type: {agent_type}. "
            f"Available: {', '.join(AGENT_TYPES.keys())}",
        }

    runner = SubAgentRunner(db)
    result = await runner.run(task=task, agent_type_name=agent_type, context=context)
    return {"agent_type": agent_type, "task": task, "result": result}


_CORE_EXECUTORS: dict[str, Any] = {
    "search_kb": _search_kb,
    "create_zettel": _create_zettel,
    "get_zettel": _get_zettel,
    "update_zettel": _update_zettel,
    "list_recent_cards": _list_recent_cards,
    "import_notes_from_filesystem": _import_notes_from_filesystem,
    "create_note": _create_note,
    "update_note": _update_note,
    "web_search_searxng": _web_search_searxng,
    "firecrawl_search": _firecrawl_search,
    "firecrawl_scrape": _firecrawl_scrape,
    "delegate_task": _delegate_task,
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
