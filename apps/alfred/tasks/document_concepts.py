from __future__ import annotations

import logging

from celery import shared_task

from alfred.core.dependencies import get_doc_storage_service

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.document_concepts.extract_document")
def extract_document_concepts_task(*, doc_id: str, force: bool = False) -> dict:
    """Extract concepts (entities/relations/topics) for a single stored document."""
    svc = get_doc_storage_service()
    logger.info("Running document concept extraction task (force=%s) for %s", force, doc_id)
    return svc.extract_document_concepts(doc_id, force=force)


@shared_task(name="alfred.tasks.document_concepts.batch_extract")
def batch_extract_document_concepts_task(
    *,
    limit: int = 100,
    min_age_hours: int = 0,
    force: bool = False,
    enqueue_only: bool = True,
) -> dict:
    """Batch-select documents and run/queue concept extraction.

    When `enqueue_only=True` (default), this task enqueues one per-document task to
    allow parallelism and limit per-task runtime.
    """
    svc = get_doc_storage_service()
    docs = svc.list_documents_needing_concepts_extraction(
        limit=int(limit),
        min_age_hours=int(min_age_hours),
        force=bool(force),
    )
    doc_ids = [str(d.id) for d in docs if getattr(d, "id", None)]
    if not doc_ids:
        return {"ok": True, "queued": 0, "doc_ids": []}

    if enqueue_only:
        task_ids: list[str] = []
        for did in doc_ids:
            async_result = extract_document_concepts_task.delay(doc_id=did, force=bool(force))
            task_ids.append(async_result.id)
        return {"ok": True, "queued": len(task_ids), "doc_ids": doc_ids, "task_ids": task_ids}

    processed: list[str] = []
    for did in doc_ids:
        extract_document_concepts_task(doc_id=did, force=bool(force))
        processed.append(did)
    return {"ok": True, "processed": len(processed), "doc_ids": processed}
