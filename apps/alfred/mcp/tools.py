"""MCP tool implementations wrapping existing Alfred services.

Includes hand-crafted tools for common operations (fast, direct DB)
and a generic HTTP proxy for the full Alfred API surface.
"""

import asyncio
import json
import logging
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import Context

from alfred.mcp.server import AlfredContext, mcp

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ALFRED_API_BASE = "http://localhost:8000"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auto-logging
# ---------------------------------------------------------------------------

_LOG_DIR = Path.home() / ".alfred"
_LOG_FILE = _LOG_DIR / "mcp-sessions.jsonl"


def _log_call(session_id: str, tool: str, **extra: Any) -> None:
    """Append a JSONL line to the session log. Best-effort, never raises."""
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "tool": tool,
            "session_id": session_id,
            **extra,
        }
        with _LOG_FILE.open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def _db_session(ctx: Context):
    """Create a scoped DB session from the lifespan context."""
    app: AlfredContext = ctx.request_context.lifespan_context
    session = app.session_factory()
    try:
        yield session
    finally:
        session.close()


def _get_app(ctx: Context) -> AlfredContext:
    return ctx.request_context.lifespan_context


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_knowledge(
    query: str,
    limit: int = 10,
    topic: str | None = None,
    ctx: Context = None,
) -> list[dict[str, Any]]:
    """Search Alfred's knowledge base for zettel cards by keyword.

    Returns matching cards ranked by relevance. Use `topic` to filter
    by knowledge domain (e.g. "system design", "AI engineering").
    """
    app = _get_app(ctx)

    def _search():
        from alfred.services.zettelkasten_service import ZettelkastenService

        with _db_session(ctx) as session:
            svc = ZettelkastenService(session=session)
            cards = svc.list_cards(q=query, topic=topic, limit=limit)
            return [
                {
                    "id": card.id,
                    "title": card.title,
                    "content_preview": (card.content or "")[:300],
                    "topic": card.topic,
                    "tags": card.tags or [],
                    "type": "zettel",
                }
                for card in cards
            ]

    try:
        results = await asyncio.to_thread(_search)
        _log_call(app.session_id, "search_knowledge", query=query, results_count=len(results))
        return results
    except Exception as e:
        logger.exception("search_knowledge failed")
        return [{"error": f"Search failed: {e}"}]


@mcp.tool()
async def get_zettel(
    zettel_id: int,
    ctx: Context = None,
) -> dict[str, Any]:
    """Retrieve a zettel card by ID with full content, metadata, and related card IDs."""
    app = _get_app(ctx)

    def _get():
        from alfred.services.zettelkasten_service import ZettelkastenService

        with _db_session(ctx) as session:
            svc = ZettelkastenService(session=session)
            card = svc.get_card(zettel_id)
            if not card:
                return {"error": f"Zettel {zettel_id} not found"}

            links = svc.list_links(card_id=card.id)
            related_ids = list(
                {
                    link.to_card_id if link.from_card_id == card.id else link.from_card_id
                    for link in links
                }
            )

            return {
                "id": card.id,
                "title": card.title,
                "content": card.content,
                "summary": card.summary,
                "topic": card.topic,
                "tags": card.tags or [],
                "created_at": card.created_at.isoformat() if card.created_at else None,
                "importance": card.importance,
                "confidence": card.confidence,
                "related_ids": related_ids,
            }

    try:
        result = await asyncio.to_thread(_get)
        _log_call(app.session_id, "get_zettel", zettel_id=zettel_id)
        return result
    except Exception as e:
        logger.exception("get_zettel failed")
        return {"error": f"Failed to get zettel: {e}"}


@mcp.tool()
async def get_document(
    document_id: str,
    ctx: Context = None,
) -> dict[str, Any]:
    """Retrieve a document by UUID with title, source URL, summary, and text preview."""
    app = _get_app(ctx)

    def _get():
        from alfred.services.doc_storage_pg import DocStorageService

        with _db_session(ctx) as session:
            svc = DocStorageService(session=session)
            details = svc.get_document_details(document_id)
            if not details:
                return {"error": f"Document {document_id} not found"}

            return {
                "id": str(details.get("id", "")),
                "title": details.get("title"),
                "source_url": details.get("source_url"),
                "summary": details.get("summary"),
                "cleaned_text_preview": (details.get("cleaned_text") or "")[:2000],
            }

    try:
        result = await asyncio.to_thread(_get)
        _log_call(app.session_id, "get_document", document_id=document_id)
        return result
    except Exception as e:
        logger.exception("get_document failed")
        return {"error": f"Failed to get document: {e}"}


@mcp.tool()
async def get_related(
    item_id: int,
    limit: int = 5,
    ctx: Context = None,
) -> list[dict[str, Any]]:
    """Find zettel cards semantically related to a given zettel card ID.

    Uses embedding similarity to find cards with related concepts.
    Requires the source card to have an embedding.
    """
    app = _get_app(ctx)

    def _find():
        from alfred.services.zettelkasten_service import ZettelkastenService

        with _db_session(ctx) as session:
            svc = ZettelkastenService(session=session)
            try:
                results = svc.find_similar_cards(item_id, threshold=0.5, limit=limit)
            except ValueError as exc:
                return [{"error": str(exc)}]

            return [
                {
                    "id": card.id,
                    "title": card.title,
                    "score": round(quality.composite_score, 3),
                    "type": "zettel",
                }
                for card, quality in results
            ]

    try:
        result = await asyncio.to_thread(_find)
        _log_call(app.session_id, "get_related", item_id=item_id, results_count=len(result))
        return result
    except Exception as e:
        logger.exception("get_related failed")
        return [{"error": f"Failed to find related cards: {e}"}]


@mcp.tool()
async def save_insight(
    title: str,
    content: str,
    topic: str,
    tags: list[str] | None = None,
    ctx: Context = None,
) -> dict[str, Any]:
    """Save a new insight as a zettel card in Alfred's knowledge base.

    The card is persisted immediately. An embedding is generated for
    future semantic search (if embedding model is available).
    """
    app = _get_app(ctx)

    def _save():
        from alfred.services.zettelkasten_service import ZettelkastenService

        with _db_session(ctx) as session:
            svc = ZettelkastenService(session=session)
            card = svc.create_card(
                title=title,
                content=content,
                topic=topic,
                tags=tags or [],
                importance=5,
                confidence=0.7,
            )

            # Best-effort embedding — card is saved regardless
            try:
                svc.ensure_embedding(card)
            except Exception:
                logger.warning("Embedding failed for card %s — card saved without embedding", card.id)

            return {
                "id": card.id,
                "title": card.title,
                "created_at": card.created_at.isoformat() if card.created_at else None,
            }

    try:
        result = await asyncio.to_thread(_save)
        _log_call(app.session_id, "save_insight", title=title)
        return result
    except Exception as e:
        logger.exception("save_insight failed")
        return {"error": f"Failed to save insight: {e}"}


# ---------------------------------------------------------------------------
# Generic API proxy — exposes the FULL Alfred API surface
# ---------------------------------------------------------------------------


@mcp.resource("alfred://openapi-spec")
async def openapi_spec() -> str:
    """Alfred's full OpenAPI specification. Read this to discover all available
    API endpoints, their parameters, request bodies, and response schemas.

    Use with the alfred_api tool to call any endpoint."""
    async with httpx.AsyncClient(base_url=ALFRED_API_BASE, timeout=10) as client:
        resp = await client.get("/openapi.json")
        resp.raise_for_status()
        return json.dumps(resp.json(), indent=2)


@mcp.tool()
async def alfred_api(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    query_params: dict[str, str] | None = None,
    ctx: Context = None,
) -> dict[str, Any]:
    """Call any Alfred API endpoint. Use the alfred://openapi-spec resource
    to discover available endpoints.

    Args:
        method: HTTP method (GET, POST, PATCH, DELETE)
        path: API path (e.g. "/api/zettels/cards", "/api/documents/explorer")
        body: JSON request body for POST/PATCH/PUT requests
        query_params: URL query parameters (e.g. {"q": "planning", "limit": "10"})

    Examples:
        - List zettels: method="GET", path="/api/zettels/cards", query_params={"limit": "5"}
        - Create zettel: method="POST", path="/api/zettels/cards", body={"title": "...", "content": "..."}
        - Search docs: method="GET", path="/api/documents/search", query_params={"q": "kubernetes"}
        - Get health: method="GET", path="/healthz"
    """
    app = _get_app(ctx)
    method = method.upper()

    if method not in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
        return {"error": f"Unsupported HTTP method: {method}"}

    try:
        async with httpx.AsyncClient(base_url=ALFRED_API_BASE, timeout=30) as client:
            resp = await client.request(
                method=method,
                url=path,
                json=body if body and method in {"POST", "PATCH", "PUT"} else None,
                params=query_params,
            )

        _log_call(app.session_id, "alfred_api", method=method, path=path, status=resp.status_code)

        # Try to parse JSON, fall back to text
        try:
            result = resp.json()
        except (json.JSONDecodeError, ValueError):
            result = {"text": resp.text[:5000]}

        if resp.status_code >= 400:
            return {
                "error": f"HTTP {resp.status_code}",
                "detail": result,
            }

        return result if isinstance(result, dict) else {"data": result}

    except httpx.ConnectError:
        return {"error": "Cannot connect to Alfred API at " + ALFRED_API_BASE + ". Is the backend running?"}
    except httpx.TimeoutException:
        return {"error": f"Request timed out: {method} {path}"}
    except Exception as e:
        logger.exception("alfred_api failed")
        return {"error": f"Request failed: {e}"}
