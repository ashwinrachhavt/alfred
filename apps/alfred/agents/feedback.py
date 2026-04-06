"""Feedback node -- saves AI conversations as documents for knowledge ingestion.

Implements the AI Panel as Connector pattern: every conversation becomes
a Document that enters the normal enrichment pipeline.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from alfred.agents.state import AlfredState
from alfred.core.database import SessionLocal
from alfred.schemas.documents import DocumentIngest
from alfred.services.doc_storage_pg import DocStorageService

logger = logging.getLogger(__name__)


def feedback_node(state: AlfredState) -> dict:
    """Save the conversation as a document for knowledge graph ingestion."""
    messages = state.get("messages", [])
    if len(messages) < 2:
        return {}

    # Format conversation as markdown
    lines = []
    for msg in messages:
        role = getattr(msg, "type", "unknown")
        content = getattr(msg, "content", str(msg))
        lines.append(f"**{role}:** {content}\n")
    markdown = "\n".join(lines)

    # Dedup hash
    content_hash = hashlib.sha256(markdown.encode()).hexdigest()[:16]
    thread_hash = f"ai_conversation:{content_hash}"

    # Extract title from first message (truncated)
    first_message_content = messages[0].content if messages else "untitled"
    if isinstance(first_message_content, list):
        # Handle multi-part messages (e.g. with images)
        first_message_content = " ".join(
            str(part.get("text", "")) if isinstance(part, dict) else str(part)
            for part in first_message_content
        )
    title = f"AI Conversation -- {str(first_message_content)[:60]}"

    try:
        session = SessionLocal()
        doc_store = DocStorageService(session=session)
        ingest = DocumentIngest(
            source_url=f"alfred://ai-conversation/{content_hash}",
            title=title,
            content_type="ai_conversation",
            raw_markdown=markdown,
            cleaned_text=markdown,
            hash=thread_hash,
            metadata={
                "source": "alfred_ai_panel",
                "intent": state.get("intent"),
                "phase": state.get("phase"),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        doc_store.ingest_document_store_only(ingest)
        logger.info("Feedback: saved conversation as document (hash=%s)", thread_hash)
    except Exception:
        logger.exception("Feedback: failed to save conversation")

    return {"phase": "done"}
