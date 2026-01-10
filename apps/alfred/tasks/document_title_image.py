from __future__ import annotations

import logging

from celery import shared_task

from alfred.core.dependencies import get_doc_storage_service

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.document_title_image.generate")
def document_title_image_task(
    *,
    doc_id: str,
    force: bool = False,
    model: str = "gpt-image-1",
    size: str = "1024x1024",
    quality: str = "high",
) -> dict:
    """Generate and store a cover image for a document."""

    svc = get_doc_storage_service()
    logger.info("Generating document title image (force=%s) for %s", force, doc_id)
    return svc.generate_document_title_image(
        doc_id,
        force=force,
        model=model,
        size=size,
        quality=quality,
    )


@shared_task(name="alfred.tasks.document_title_image.batch_generate")
def batch_generate_document_title_images_task(
    *,
    limit: int = 100,
    min_age_hours: int = 0,
    force: bool = False,
    enqueue_only: bool = True,
    model: str = "gpt-image-1",
    size: str = "1024x1024",
    quality: str = "high",
) -> dict:
    """Batch-select documents and run/queue title image generation.

    When `enqueue_only=True` (default), this task enqueues one per-document task to
    allow parallelism and limit per-task runtime.
    """

    svc = get_doc_storage_service()
    docs = svc.list_documents_needing_title_images(
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
            async_result = document_title_image_task.delay(
                doc_id=did,
                force=bool(force),
                model=str(model),
                size=str(size),
                quality=str(quality),
            )
            task_ids.append(async_result.id)
        return {"ok": True, "queued": len(task_ids), "doc_ids": doc_ids, "task_ids": task_ids}

    processed: list[str] = []
    for did in doc_ids:
        document_title_image_task(
            doc_id=did,
            force=bool(force),
            model=str(model),
            size=str(size),
            quality=str(quality),
        )
        processed.append(did)
    return {"ok": True, "processed": len(processed), "doc_ids": processed}
