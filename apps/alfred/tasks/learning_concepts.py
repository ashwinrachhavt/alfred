from __future__ import annotations

import logging

from celery import shared_task

from alfred.core.database import SessionLocal
from alfred.services.learning_service import LearningService

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.learning_concepts.extract_resource")
def extract_learning_resource_concepts_task(*, resource_id: int, force: bool = False) -> dict:
    """Extract concepts for a single learning resource."""
    session = SessionLocal()
    try:
        svc = LearningService(session)
        resource = svc.get_resource(int(resource_id))
        if not resource:
            raise ValueError("Resource not found")
        if (not force) and resource.extracted_at:
            return {"ok": True, "skipped": True, "resource_id": int(resource_id)}
        graph = svc.extract_resource_concepts(resource=resource)
        return {"ok": True, "skipped": False, "resource_id": int(resource_id), "graph": graph}
    finally:
        session.close()


@shared_task(name="alfred.tasks.learning_concepts.batch_extract")
def batch_extract_learning_concepts_task(
    *,
    limit: int = 50,
    topic_id: int | None = None,
    min_age_hours: int = 0,
    force: bool = False,
    enqueue_only: bool = True,
) -> dict:
    """Batch-select learning resources and run/queue concept extraction.

    When `enqueue_only=True` (default), this task enqueues one per-resource task to
    allow parallelism and limit per-task runtime.
    """
    session = SessionLocal()
    try:
        svc = LearningService(session)
        resources = svc.list_resources_needing_extraction(
            limit=int(limit),
            topic_id=topic_id,
            min_age_hours=int(min_age_hours),
            force=bool(force),
        )
        resource_ids = [int(r.id or 0) for r in resources if (r.id or 0) > 0]
        if not resource_ids:
            return {"ok": True, "queued": 0, "resource_ids": []}

        if enqueue_only:
            task_ids: list[str] = []
            for rid in resource_ids:
                async_result = extract_learning_resource_concepts_task.delay(
                    resource_id=rid, force=bool(force)
                )
                task_ids.append(async_result.id)
            return {
                "ok": True,
                "queued": len(task_ids),
                "resource_ids": resource_ids,
                "task_ids": task_ids,
            }

        processed: list[int] = []
        for rid in resource_ids:
            extract_learning_resource_concepts_task(resource_id=rid, force=bool(force))
            processed.append(rid)
        return {"ok": True, "processed": len(processed), "resource_ids": processed}
    finally:
        session.close()
