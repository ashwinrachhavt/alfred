from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from alfred.core.settings import settings
from alfred.schemas.job_applications import (
    JobApplicationCreate,
    JobApplicationRecord,
    JobApplicationStatus,
    JobApplicationUpdate,
)
from alfred.services.datastore import DataStoreService


def _utcnow() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


@dataclass
class JobApplicationService:
    """Postgres-backed CRUD for job applications."""

    collection_name: str = settings.job_applications_collection

    def __post_init__(self) -> None:
        self._collection = DataStoreService(default_collection=self.collection_name)

    def ensure_indexes(self) -> None:  # indexes are managed via Alembic
        return

    def create(self, payload: JobApplicationCreate) -> str:
        now = _utcnow()
        doc = {
            "company": payload.company,
            "role": payload.role,
            "status": JobApplicationStatus.applied.value,
            "source_url": payload.source_url,
            "metadata": payload.metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        return self._collection.insert_one(doc)

    def get(self, job_application_id: str) -> Optional[Dict[str, Any]]:
        doc = self._collection.find_one({"_id": job_application_id})
        if not doc:
            return None
        JobApplicationRecord.model_validate(doc)
        out = dict(doc)
        out["id"] = str(out.pop("_id"))
        return out

    def update(self, job_application_id: str, patch: JobApplicationUpdate) -> bool:
        update: dict[str, Any] = {"updated_at": patch.updated_at or _utcnow()}
        if patch.status is not None:
            update["status"] = patch.status.value
        if patch.source_url is not None:
            update["source_url"] = patch.source_url
        if patch.metadata is not None:
            update["metadata"] = patch.metadata
        res = self._collection.update_one({"_id": job_application_id}, {"$set": update})
        return bool(res.get("matched_count", 0))


__all__ = ["JobApplicationService"]
