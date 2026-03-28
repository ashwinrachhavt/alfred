"""Celery task to run the document ingestion pipeline."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


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
        return {
            "doc_id": doc_id,
            "status": "completed",
            "stage": result.get("stage"),
            "cache_hits": result.get("cache_hits", []),
            "errors": result.get("errors", []),
        }
    except Exception as exc:
        logger.exception("Pipeline failed for %s", doc_id)
        raise self.retry(exc=exc) from exc
