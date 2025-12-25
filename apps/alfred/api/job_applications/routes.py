from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from alfred.core.dependencies import get_job_application_service
from alfred.core.utils import clamp_int
from alfred.schemas.job_applications import (
    JobApplicationCreate,
    JobApplicationStatus,
    JobApplicationUpdate,
)
from alfred.services.job_hunt_service import JobApplicationService

router = APIRouter(prefix="/api/job_applications", tags=["job_applications"])


@router.post("")
def create_job_application(
    payload: JobApplicationCreate,
    svc: JobApplicationService = Depends(get_job_application_service),
) -> dict[str, Any]:
    job_id = svc.create(payload)
    return {"id": job_id}


@router.get("/{job_application_id}")
def get_job_application(
    job_application_id: str,
    svc: JobApplicationService = Depends(get_job_application_service),
) -> dict[str, Any]:
    record = svc.get(job_application_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job application not found")
    return record


class JobApplicationPatch(BaseModel):
    status: JobApplicationStatus | None = None
    source_url: str | None = None
    metadata: dict[str, Any] | None = None


@router.patch("/{job_application_id}")
def patch_job_application(
    job_application_id: str,
    payload: JobApplicationPatch,
    svc: JobApplicationService = Depends(get_job_application_service),
) -> dict[str, Any]:
    ok = svc.update(
        job_application_id,
        JobApplicationUpdate(
            status=payload.status,
            source_url=payload.source_url,
            metadata=payload.metadata,
        ),
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Job application not found")
    return {"ok": True}


@router.get("")
def list_job_applications(
    status: JobApplicationStatus | None = None,
    limit: int = 20,
    svc: JobApplicationService = Depends(get_job_application_service),
) -> dict[str, Any]:
    lim = clamp_int(limit, lo=1, hi=100)
    filt: dict[str, Any] = {}
    if status is not None:
        filt["status"] = status.value
    docs = (
        svc._collection.find(
            filt, projection={"company": 1, "role": 1, "status": 1, "updated_at": 1}
        )
        .sort("updated_at", -1)
        .limit(lim)
    )
    items = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        items.append(d)
    return {"count": len(items), "items": items}


__all__ = ["router"]
