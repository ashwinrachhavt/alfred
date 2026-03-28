"""Pipeline replay and status API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from alfred.core.celery_client import get_celery_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


def _get_checkpointer():
    from alfred.core.settings import settings
    from alfred.services.checkpoint_postgres import (
        PostgresCheckpointConfig,
        PostgresCheckpointSaver,
    )

    dsn = settings.writer_checkpoint_dsn or settings.database_url.replace(
        "postgresql+psycopg", "postgresql"
    )
    return PostgresCheckpointSaver(cfg=PostgresCheckpointConfig(dsn=dsn))


@router.post("/{doc_id}/replay", status_code=202)
def replay_document(
    doc_id: str,
    from_stage: str | None = Query(None),
    force: bool = Query(False),
):
    """Replay the pipeline for a document. Dispatches to Celery."""
    celery_client = get_celery_client()
    async_result = celery_client.send_task(
        "alfred.tasks.document_pipeline.run_document_pipeline",
        kwargs={
            "doc_id": doc_id,
            "force_replay": force,
            "replay_from": from_stage,
        },
    )

    return {
        "doc_id": doc_id,
        "task_id": async_result.id,
        "from_stage": from_stage,
        "force": force,
    }


@router.get("/{doc_id}/status")
def pipeline_status(doc_id: str):
    """Get the current pipeline state for a document."""
    checkpointer = _get_checkpointer()
    thread_id = f"pipeline:{doc_id}"

    checkpoint = checkpointer.get_tuple(
        {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    )
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="No pipeline run found")

    values = checkpoint.checkpoint.get("channel_values", {})
    return {
        "doc_id": doc_id,
        "stage": values.get("stage"),
        "errors": values.get("errors", []),
        "cache_hits": values.get("cache_hits", []),
        "embedding_indexed": values.get("embedding_indexed", False),
    }


@router.post("/replay-batch", status_code=202)
def replay_batch(
    force: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
):
    """Replay pipeline for documents missing enrichment."""
    from alfred.core.dependencies import get_doc_storage_service

    celery_client = get_celery_client()
    svc = get_doc_storage_service()
    docs = svc.list_documents_needing_concepts_extraction(limit=limit)

    task_ids = []
    for doc in docs:
        doc_id = str(doc.id) if hasattr(doc, "id") else str(doc["id"])
        async_result = celery_client.send_task(
            "alfred.tasks.document_pipeline.run_document_pipeline",
            kwargs={
                "doc_id": doc_id,
                "force_replay": force,
            },
        )
        task_ids.append({"doc_id": doc_id, "task_id": async_result.id})

    return {"queued": len(task_ids), "tasks": task_ids}
