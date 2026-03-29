"""Celery task to run the document ingestion pipeline."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def _set_pipeline_status(doc_id: str, status: str) -> None:
    """Update the pipeline_status column on a document row."""
    try:
        from datetime import UTC, datetime

        from alfred.core.database import engine
        from alfred.models.doc_storage import DocumentRow
        from alfred.services.doc_storage.utils import parse_uuid as _parse_uuid

        uid = _parse_uuid(doc_id)
        if uid is None:
            return

        from sqlmodel import Session as SMSession

        with SMSession(engine) as session:
            doc = session.get(DocumentRow, uid)
            if doc:
                doc.pipeline_status = status
                if status == "complete":
                    doc.processed_at = datetime.now(UTC)
                session.add(doc)
                session.commit()
    except Exception:
        logger.warning(
            "Failed to set pipeline_status=%s for %s", status, doc_id, exc_info=True
        )


@shared_task(
    name="alfred.tasks.document_pipeline.run_document_pipeline",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
)
def run_document_pipeline(
    self,
    *,
    doc_id: str,
    user_id: str = "",
    force_replay: bool = False,
    replay_from: str | None = None,
) -> dict:
    """Run the document pipeline graph for a single document."""
    from alfred.core.settings import settings
    from alfred.pipeline.graph import build_pipeline_graph
    from alfred.services.checkpoint_postgres import (
        PostgresCheckpointConfig,
        PostgresCheckpointSaver,
    )

    _set_pipeline_status(doc_id, "processing")

    dsn = settings.writer_checkpoint_dsn or settings.database_url.replace(
        "postgresql+psycopg", "postgresql"
    )

    checkpointer = PostgresCheckpointSaver(
        cfg=PostgresCheckpointConfig(dsn=dsn)
    )
    graph = build_pipeline_graph(checkpointer=checkpointer)

    initial_state = {
        "doc_id": doc_id,
        "user_id": user_id,
        "errors": [],
        "cache_hits": [],
        "force_replay": force_replay,
        "replay_from": replay_from,
    }

    thread_id = f"pipeline:{doc_id}"
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = graph.invoke(initial_state, config=config)
        logger.info(
            "Pipeline completed for %s: stage=%s, cache_hits=%s",
            doc_id,
            result.get("stage"),
            result.get("cache_hits"),
        )
        _set_pipeline_status(doc_id, "complete")
        return {
            "doc_id": doc_id,
            "status": "completed",
            "stage": result.get("stage"),
            "cache_hits": result.get("cache_hits", []),
            "errors": result.get("errors", []),
        }
    except Exception as exc:
        logger.exception("Pipeline failed for %s", doc_id)
        _set_pipeline_status(doc_id, "error")
        raise self.retry(exc=exc) from exc
