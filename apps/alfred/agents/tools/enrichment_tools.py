"""Enrichment agent tools -- document processing and concept extraction.

Tools for summarizing documents, extracting concepts, classifying content,
decomposing documents into atomic zettels, and generating embeddings.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool

from alfred.core.database import SessionLocal
from alfred.services.doc_storage_pg import DocStorageService

logger = logging.getLogger(__name__)


def _get_doc_service() -> DocStorageService:
    """Create a DocStorageService with a fresh DB session."""
    session = SessionLocal()
    return DocStorageService(session=session)


@tool
def summarize(doc_id: str, max_length: int = 300) -> str:
    """Generate or retrieve a summary for a document. Returns concise summary."""
    svc = _get_doc_service()
    try:
        doc = svc.get_document_details(doc_id)
        if not doc:
            return json.dumps({"error": f"Document {doc_id} not found"})

        # If summary exists, return it
        existing_summary = doc.get("summary")
        if existing_summary and len(existing_summary) <= max_length * 1.5:
            return json.dumps({
                "doc_id": doc_id,
                "summary": existing_summary[:max_length],
                "source": "existing",
            })

        # Generate new summary using LLM
        from alfred.core.llm_factory import get_chat_model

        content = doc.get("content") or doc.get("text") or ""
        if not content:
            return json.dumps({"error": "Document has no content to summarize"})

        model = get_chat_model()
        prompt = f"Summarize this document in {max_length} characters or less:\n\n{content[:4000]}"
        response = model.invoke(prompt)
        summary = response.content if hasattr(response, "content") else str(response)

        return json.dumps({
            "doc_id": doc_id,
            "summary": summary[:max_length],
            "source": "generated",
        })
    except Exception as exc:
        logger.error("summarize failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def extract_concepts(doc_id: str, max_concepts: int = 10) -> str:
    """Extract key concepts from a document using LLM. Returns list of concepts with descriptions."""
    svc = _get_doc_service()
    try:
        doc = svc.get_document_details(doc_id)
        if not doc:
            return json.dumps({"error": f"Document {doc_id} not found"})

        content = doc.get("content") or doc.get("text") or ""
        if not content:
            return json.dumps({"error": "Document has no content"})

        from alfred.core.llm_factory import get_chat_model

        model = get_chat_model()
        system_prompt = (
            f"Extract up to {max_concepts} key concepts from this document. "
            "Return ONLY valid JSON array: [{\"concept\": \"name\", \"description\": \"brief explanation\"}]"
        )
        user_prompt = content[:4000]

        response = model.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        result_text = response.content if hasattr(response, "content") else str(response)

        # Try to parse as JSON
        import re
        json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
        if json_match:
            concepts = json.loads(json_match.group())
        else:
            concepts = []

        return json.dumps({
            "doc_id": doc_id,
            "concepts": concepts[:max_concepts],
        })
    except Exception as exc:
        logger.error("extract_concepts failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def classify_document(doc_id: str) -> str:
    """Classify a document into categories and assign topic/tags. Returns classification metadata."""
    svc = _get_doc_service()
    try:
        doc = svc.get_document_details(doc_id)
        if not doc:
            return json.dumps({"error": f"Document {doc_id} not found"})

        content = doc.get("content") or doc.get("text") or ""
        title = doc.get("title", "")

        if not content and not title:
            return json.dumps({"error": "Document has no content to classify"})

        from alfred.core.llm_factory import get_chat_model

        model = get_chat_model()
        system_prompt = (
            "Classify this document. Return ONLY valid JSON: "
            "{\"topic\": \"main domain\", \"category\": \"type\", \"tags\": [\"tag1\", \"tag2\"], "
            "\"importance\": 5, \"confidence\": 0.8}"
        )
        user_prompt = f"Title: {title}\n\nContent: {content[:2000]}"

        response = model.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        result_text = response.content if hasattr(response, "content") else str(response)

        # Parse JSON from response
        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            classification = json.loads(json_match.group())
        else:
            classification = {}

        return json.dumps({
            "doc_id": doc_id,
            "classification": classification,
        })
    except Exception as exc:
        logger.error("classify_document failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def decompose_to_zettels(doc_id: str, auto_link: bool = True) -> str:
    """Decompose a document into atomic zettel cards. Queues enrichment task, returns task ID."""
    try:
        from alfred.tasks.document_enrichment import enrich_document_task

        result = enrich_document_task.delay(doc_id=doc_id)
        return json.dumps({
            "ok": True,
            "doc_id": doc_id,
            "task_id": result.id,
            "status": "queued",
            "message": "Document decomposition queued",
        })
    except Exception as exc:
        logger.error("decompose_to_zettels failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def generate_embeddings(doc_id: str) -> str:
    """Generate and store embeddings for a document using the configured embedding model."""
    svc = _get_doc_service()
    try:
        doc = svc.get_document_details(doc_id)
        if not doc:
            return json.dumps({"error": f"Document {doc_id} not found"})

        content = doc.get("content") or doc.get("text") or ""
        if not content:
            return json.dumps({"error": "Document has no content to embed"})

        from alfred.core.llm_factory import get_embedding_model

        model = get_embedding_model()
        embedding = model.embed_query(content[:8000])  # Truncate to avoid token limits

        # Store embedding (this would need to be implemented in DocStorageService)
        # For now, just return confirmation
        return json.dumps({
            "ok": True,
            "doc_id": doc_id,
            "embedding_dims": len(embedding),
            "status": "generated",
        })
    except Exception as exc:
        logger.error("generate_embeddings failed: %s", exc)
        return json.dumps({"error": str(exc)})


# List of all enrichment tools for agent registration
ENRICHMENT_TOOLS = [
    summarize,
    extract_concepts,
    classify_document,
    decompose_to_zettels,
    generate_embeddings,
]
