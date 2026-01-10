from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from alfred.api.dependencies import get_db_session
from alfred.core.celery_client import get_celery_client
from alfred.core.settings import settings
from alfred.models.doc_storage import DocumentRow
from alfred.models.learning import LearningResource
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.learning_service import LearningService

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    include_in_schema=bool(settings.enable_admin_api_schema),
)


@router.get("/learning/concepts/backlog")
def learning_concepts_backlog(
    limit: int = Query(20, ge=1, le=200),
    topic_id: int | None = Query(None),
    min_age_hours: int = Query(0, ge=0, le=168),
    session: Session = Depends(get_db_session),
) -> dict:
    """Operational view: how many learning resources still need concept extraction."""

    svc = LearningService(session)
    candidates = svc.list_resources_needing_extraction(
        limit=limit,
        topic_id=topic_id,
        min_age_hours=min_age_hours,
        force=False,
    )
    sample_ids = [int(r.id or 0) for r in candidates if (r.id or 0) > 0]

    base = (
        select(func.count())
        .select_from(LearningResource)
        .where(LearningResource.document_id.is_not(None))
    )
    base = base.where(func.length(func.trim(LearningResource.document_id)) > 0)
    if topic_id is not None:
        base = base.where(LearningResource.topic_id == int(topic_id))
    if min_age_hours and min_age_hours > 0:
        cutoff = datetime.utcnow() - timedelta(hours=int(min_age_hours))
        base = base.where(LearningResource.added_at <= cutoff)

    pending_stmt = base.where(LearningResource.extracted_at.is_(None))
    total_with_doc_stmt = base

    pending_count = int(session.exec(pending_stmt).one() or 0)
    total_with_document = int(session.exec(total_with_doc_stmt).one() or 0)

    return {
        "pending_count": pending_count,
        "total_with_document": total_with_document,
        "sample_resource_ids": sample_ids,
        "nightly": {
            "enabled": bool(settings.enable_learning_concept_extraction_nightly),
            "utc_hour": int(settings.learning_concept_extraction_nightly_hour),
            "utc_minute": int(settings.learning_concept_extraction_nightly_minute),
            "batch_limit": int(settings.learning_concept_extraction_batch_limit),
            "min_age_hours": int(settings.learning_concept_extraction_min_age_hours),
        },
    }


class _BatchEnqueueRequest(BaseModel):
    limit: int = Field(default=0, ge=0, le=500)
    topic_id: int | None = None
    min_age_hours: int = Field(default=0, ge=0, le=168)
    force: bool = False


@router.post("/learning/concepts/extract/batch/async")
def enqueue_learning_concepts_batch(payload: _BatchEnqueueRequest) -> dict:
    """Admin trigger: enqueue a batch concept-extraction run immediately."""

    limit = int(payload.limit or settings.learning_concept_extraction_batch_limit)
    min_age_hours = int(
        payload.min_age_hours
        if payload.min_age_hours is not None
        else settings.learning_concept_extraction_min_age_hours
    )

    celery_client = get_celery_client()
    async_result = celery_client.send_task(
        "alfred.tasks.learning_concepts.batch_extract",
        kwargs={
            "limit": limit,
            "topic_id": int(payload.topic_id) if payload.topic_id is not None else None,
            "min_age_hours": min_age_hours,
            "force": bool(payload.force),
            "enqueue_only": True,
        },
    )
    return {
        "status": "queued",
        "task_id": async_result.id,
        "status_url": f"/tasks/{async_result.id}",
        "kwargs": {
            "limit": limit,
            "topic_id": int(payload.topic_id) if payload.topic_id is not None else None,
            "min_age_hours": min_age_hours,
            "force": bool(payload.force),
            "enqueue_only": True,
        },
    }


@router.get("/documents/concepts/backlog")
def document_concepts_backlog(
    limit: int = Query(20, ge=1, le=200),
    min_age_hours: int = Query(0, ge=0, le=168),
    session: Session = Depends(get_db_session),
) -> dict:
    """Operational view: how many documents still need concept extraction."""

    svc = DocStorageService(session=session)
    candidates = svc.list_documents_needing_concepts_extraction(
        limit=limit,
        min_age_hours=min_age_hours,
        force=False,
    )
    sample_ids = [str(d.id) for d in candidates if getattr(d, "id", None)]

    base = select(func.count()).select_from(DocumentRow)
    if min_age_hours and min_age_hours > 0:
        cutoff = datetime.utcnow() - timedelta(hours=int(min_age_hours))
        base = base.where(DocumentRow.created_at <= cutoff)

    pending_stmt = base.where(DocumentRow.concepts_extracted_at.is_(None))
    pending_count = int(session.exec(pending_stmt).one() or 0)
    total_count = int(session.exec(base).one() or 0)

    return {
        "pending_count": pending_count,
        "total": total_count,
        "sample_doc_ids": sample_ids,
        "nightly": {
            "enabled": bool(settings.enable_document_concept_extraction_nightly),
            "utc_hour": int(settings.document_concept_extraction_nightly_hour),
            "utc_minute": int(settings.document_concept_extraction_nightly_minute),
            "batch_limit": int(settings.document_concept_extraction_batch_limit),
            "min_age_hours": int(settings.document_concept_extraction_min_age_hours),
        },
    }


class _DocumentBatchEnqueueRequest(BaseModel):
    limit: int = Field(default=0, ge=0, le=500)
    min_age_hours: int = Field(default=0, ge=0, le=168)
    force: bool = False


@router.post("/documents/concepts/extract/batch/async")
def enqueue_document_concepts_batch(payload: _DocumentBatchEnqueueRequest) -> dict:
    """Admin trigger: enqueue a batch concept-extraction run for documents immediately."""

    limit = int(payload.limit or settings.document_concept_extraction_batch_limit)
    min_age_hours = int(
        payload.min_age_hours
        if payload.min_age_hours is not None
        else settings.document_concept_extraction_min_age_hours
    )

    celery_client = get_celery_client()
    async_result = celery_client.send_task(
        "alfred.tasks.document_concepts.batch_extract",
        kwargs={
            "limit": limit,
            "min_age_hours": min_age_hours,
            "force": bool(payload.force),
            "enqueue_only": True,
        },
    )
    return {
        "status": "queued",
        "task_id": async_result.id,
        "status_url": f"/tasks/{async_result.id}",
        "kwargs": {
            "limit": limit,
            "min_age_hours": min_age_hours,
            "force": bool(payload.force),
            "enqueue_only": True,
        },
    }
