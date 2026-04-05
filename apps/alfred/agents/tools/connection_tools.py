"""Connection agent tools -- linking, similarity, and batch processing.

Tools for discovering and creating connections between zettel cards using
semantic similarity, tag overlap, and other heuristics.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool

from alfred.core.database import SessionLocal
from alfred.services.zettelkasten_service import ZettelkastenService

logger = logging.getLogger(__name__)


def _get_zettel_service() -> ZettelkastenService:
    """Create a ZettelkastenService with a fresh DB session."""
    session = SessionLocal()
    return ZettelkastenService(session=session)


@tool
def find_similar(zettel_id: int, threshold: float = 0.7, limit: int = 10) -> str:
    """Find similar zettel cards using semantic similarity. Returns cards above threshold."""
    svc = _get_zettel_service()
    try:
        results = svc.find_similar_cards(zettel_id, threshold=threshold, limit=limit)
        output = [
            {
                "id": card.id,
                "title": card.title,
                "topic": card.topic,
                "tags": card.tags,
                "semantic_score": quality.semantic_score,
                "composite_score": quality.composite_score,
                "tag_overlap": quality.tag_overlap,
                "topic_match": quality.topic_match,
            }
            for card, quality in results
        ]
        return json.dumps(output)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    except Exception as exc:
        logger.error("find_similar failed: %s", exc)
        return json.dumps({"error": "Failed to find similar cards"})


@tool
def suggest_links(zettel_id: int, min_confidence: float = 0.6, limit: int = 10) -> str:
    """Suggest potential links for a zettel card based on similarity and context."""
    svc = _get_zettel_service()
    try:
        suggestions = svc.suggest_links(zettel_id, min_confidence=min_confidence, limit=limit)
        output = [
            {
                "to_card_id": s.to_card_id,
                "to_title": s.to_title,
                "to_topic": s.to_topic,
                "to_tags": s.to_tags,
                "reason": s.reason,
                "composite_score": s.scores.composite_score,
            }
            for s in suggestions
        ]
        return json.dumps(output)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    except Exception as exc:
        logger.error("suggest_links failed: %s", exc)
        return json.dumps({"error": "Failed to suggest links"})


@tool
def create_link(from_card_id: int, to_card_id: int, link_type: str = "reference", context: str | None = None, bidirectional: bool = True) -> str:
    """Create a link between two zettel cards. Types: reference, comparison, contradiction, elaboration."""
    svc = _get_zettel_service()
    try:
        links = svc.create_link(
            from_card_id=from_card_id,
            to_card_id=to_card_id,
            type=link_type,
            context=context,
            bidirectional=bidirectional,
        )
        return json.dumps({
            "ok": True,
            "links_created": len(links),
            "from_card_id": from_card_id,
            "to_card_id": to_card_id,
            "type": link_type,
        })
    except Exception as exc:
        logger.error("create_link failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def get_card_links(zettel_id: int) -> str:
    """Get all links connected to a zettel card (both incoming and outgoing)."""
    svc = _get_zettel_service()
    try:
        links = svc.list_links(card_id=zettel_id)
        output = [
            {
                "id": link.id,
                "from_card_id": link.from_card_id,
                "to_card_id": link.to_card_id,
                "type": link.type,
                "context": link.context,
                "bidirectional": link.bidirectional,
            }
            for link in links
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.error("get_card_links failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def batch_link(limit: int = 50, max_existing_links: int = 3, min_confidence: float = 0.6, auto_link: bool = True) -> str:
    """Queue batch link generation for cards with few existing links. Returns task IDs."""
    try:
        from alfred.tasks.batch_linking import batch_link_task

        result = batch_link_task.delay(
            limit=limit,
            max_existing_links=max_existing_links,
            min_confidence=min_confidence,
            auto_link=auto_link,
            enqueue_only=True,
        )
        return json.dumps({
            "ok": True,
            "task_id": result.id,
            "status": "queued",
            "message": f"Batch linking queued for up to {limit} cards",
        })
    except Exception as exc:
        logger.error("batch_link failed: %s", exc)
        return json.dumps({"error": str(exc)})


# List of all connection tools for agent registration
CONNECTION_TOOLS = [find_similar, suggest_links, create_link, get_card_links, batch_link]
