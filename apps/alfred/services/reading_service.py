"""Reading session service — orchestrates tracking, ingestion, and AI features.

Thin orchestrator that delegates to existing services (DocStorageService,
agentic_rag, LLMService) for heavy lifting.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import func, select
from sqlmodel import Session

from alfred.core.utils import utcnow as _utcnow
from alfred.models.reading import ReadingSessionRow
from alfred.schemas.documents import DocumentIngest
from alfred.services.doc_storage._session import _session_scope
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.llm_service import LLMService

logger = logging.getLogger(__name__)

CAPTURE_THRESHOLD = 40


class ReadingService:
    """Orchestrates reading tracking, capture, and AI companion features."""

    def __init__(
        self,
        *,
        doc_storage: DocStorageService,
        llm_service: LLMService,
        session: Session | None = None,
    ) -> None:
        self.doc_storage = doc_storage
        self.llm_service = llm_service
        self.session = session

    # ------------------------------------------------------------------
    # Tracking
    # ------------------------------------------------------------------

    def track_events(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """Bulk insert ReadingSession rows from a batch of events.

        Returns ``{received: N, ingested: N}`` where *ingested* counts events
        above the capture threshold that triggered document ingestion.
        """
        received = len(events)
        ingested = 0

        with _session_scope(self.session) as s:
            for ev in events:
                url = ev.get("url", "")
                row = ReadingSessionRow(
                    url=url,
                    url_hash=ReadingSessionRow.hash_url(url),
                    title=ev.get("title"),
                    domain=ev.get("domain"),
                    engagement_score=ev.get("score", 0),
                    active_time_ms=ev.get("active_time_ms", 0),
                    scroll_depth=ev.get("scroll_depth", 0),
                    selection_count=ev.get("selection_count", 0),
                    copy_count=ev.get("copy_count", 0),
                    is_revisit=ev.get("is_revisit", False),
                    captured=False,
                )
                s.add(row)

                if row.engagement_score >= CAPTURE_THRESHOLD:
                    ingested += 1

            s.commit()

        return {"received": received, "ingested": ingested}

    # ------------------------------------------------------------------
    # Ingestion (high-engagement page capture)
    # ------------------------------------------------------------------

    def ingest_page(
        self,
        *,
        url: str,
        title: str | None,
        text: str,
        html: str | None = None,
        engagement_score: int = 0,
        active_time_ms: int = 0,
        scroll_depth: int = 0,
    ) -> dict[str, Any]:
        """Capture a page into the document store and record a ReadingSession."""

        # Store the document via existing pipeline
        ingest = DocumentIngest(
            source_url=url,
            title=title,
            cleaned_text=text,
            content_type="web",
        )
        res = self.doc_storage.ingest_document_store_only(ingest)
        document_id = res.get("id")

        # Record reading session with captured=True
        with _session_scope(self.session) as s:
            row = ReadingSessionRow(
                url=url,
                url_hash=ReadingSessionRow.hash_url(url),
                title=title,
                domain=_extract_domain(url),
                engagement_score=engagement_score,
                active_time_ms=active_time_ms,
                scroll_depth=scroll_depth,
                captured=True,
            )
            s.add(row)
            s.commit()

        status = "duplicate" if res.get("duplicate") else "captured"
        return {"document_id": document_id, "status": status}

    # ------------------------------------------------------------------
    # AI Companion — Connections
    # ------------------------------------------------------------------

    def get_connections(self, text: str, limit: int = 5) -> list[dict[str, Any]]:
        """Find semantically related items from the knowledge base."""
        from alfred.services.agentic_rag import get_context_chunks

        chunks = get_context_chunks(text[:2000], k=limit)
        connections = []
        for chunk in chunks:
            connections.append({
                "title": chunk.get("title"),
                "source_url": chunk.get("source"),
                "text": chunk.get("text", "")[:300],
            })
        return connections

    # ------------------------------------------------------------------
    # AI Companion — Decompose
    # ------------------------------------------------------------------

    def decompose_article(self, text: str, title: str) -> dict[str, Any]:
        """Extract claims, summary, and open questions from article text."""

        system_prompt = (
            "You are a knowledge analyst. Given an article, extract structured claims.\n"
            "Return valid JSON with this exact structure:\n"
            "{\n"
            '  "summary": "2-3 sentence summary",\n'
            '  "claims": [\n'
            '    {"text": "claim text", "tag": "testable_claim|design_principle|opinion|definition"}\n'
            "  ],\n"
            '  "open_questions": ["question 1", "question 2"]\n'
            "}\n\n"
            "Tags:\n"
            "- testable_claim: falsifiable factual assertion\n"
            "- design_principle: architectural/design guidance\n"
            "- opinion: subjective position or value judgment\n"
            "- definition: defines a term or concept\n\n"
            "Extract 5-15 claims. Return ONLY valid JSON, no markdown fences."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Title: {title}\n\nArticle:\n{text[:8000]}"},
        ]

        raw = self.llm_service.chat(messages, temperature=0.2)

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON for decompose; wrapping raw text")
            result = {
                "summary": raw[:500],
                "claims": [],
                "open_questions": [],
            }

        return result

    # ------------------------------------------------------------------
    # AI Companion — Chat (streaming)
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        *,
        text: str,
        message: str,
        chat_history: list[dict[str, str]] | None = None,
        connections: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        """Async generator that yields JSON chunks for streaming chat."""

        # Build context from article + connections
        context_parts = [f"Article text (first 4000 chars):\n{text[:4000]}"]
        if connections:
            conn_text = "\n".join(
                f"- {c.get('title', 'Untitled')}: {c.get('text', '')[:200]}"
                for c in connections[:5]
            )
            context_parts.append(f"\nRelated knowledge:\n{conn_text}")

        system_prompt = (
            "You are Alfred, a knowledge companion. The user is reading an article and "
            "wants to discuss it. Use the article text and related knowledge from their "
            "knowledge base to give insightful, concise answers. "
            "Be direct and analytical."
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n".join(context_parts)},
        ]

        # Append chat history
        for entry in (chat_history or []):
            role = entry.get("role", "user")
            content = entry.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        # Current message
        messages.append({"role": "user", "content": message})

        # Stream via LLM service
        for chunk in self.llm_service.chat_stream(messages):
            yield json.dumps({"content": chunk}) + "\n"

        # Final done marker
        yield json.dumps({"content": "", "done": True}) + "\n"

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_history(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        domain: str | None = None,
        min_score: int | None = None,
    ) -> dict[str, Any]:
        """Query reading sessions with optional filters."""

        with _session_scope(self.session) as s:
            query = select(ReadingSessionRow)
            count_query = select(func.count()).select_from(ReadingSessionRow)

            if domain:
                query = query.where(ReadingSessionRow.domain == domain)
                count_query = count_query.where(ReadingSessionRow.domain == domain)
            if min_score is not None:
                query = query.where(ReadingSessionRow.engagement_score >= min_score)
                count_query = count_query.where(
                    ReadingSessionRow.engagement_score >= min_score
                )

            total = s.exec(count_query).one()

            query = query.order_by(ReadingSessionRow.created_at.desc())  # type: ignore[union-attr]
            query = query.offset(offset).limit(limit)
            rows = s.exec(query).all()

            items = []
            for row in rows:
                items.append({
                    "id": str(row.id),
                    "url": row.url,
                    "title": row.title,
                    "domain": row.domain,
                    "engagement_score": row.engagement_score,
                    "active_time_ms": row.active_time_ms,
                    "scroll_depth": row.scroll_depth,
                    "selection_count": row.selection_count,
                    "copy_count": row.copy_count,
                    "is_revisit": row.is_revisit,
                    "captured": row.captured,
                    "document_id": str(row.document_id) if row.document_id else None,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                })

        return {"items": items, "total": total}


def _extract_domain(url: str) -> str | None:
    """Extract domain from a URL."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc or None
    except Exception:
        return None
