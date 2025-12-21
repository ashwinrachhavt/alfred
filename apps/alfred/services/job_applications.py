from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database

from alfred.core.settings import settings
from alfred.schemas.job_applications import (
    JobApplicationCreate,
    JobApplicationRecord,
    JobApplicationStatus,
    JobApplicationUpdate,
)


def _utcnow() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


@dataclass
class JobApplicationService:
    """Mongo-backed CRUD for job applications."""

    database: Database | None = None
    collection_name: str = settings.job_applications_collection

    def __post_init__(self) -> None:
        if self.database is None:
            from alfred.connectors.mongo_connector import MongoConnector

            self.database = MongoConnector().database
        self._collection: Collection = self.database.get_collection(self.collection_name)

    def ensure_indexes(self) -> None:
        try:
            self._collection.create_index([("company", 1), ("role", 1)], name="company_role")
            self._collection.create_index([("status", 1)], name="status")
            self._collection.create_index([("updated_at", -1)], name="updated_desc")
        except Exception:
            pass

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
        res = self._collection.insert_one(doc)
        return str(res.inserted_id)

    def get(self, job_application_id: str) -> Optional[Dict[str, Any]]:
        if not ObjectId.is_valid(job_application_id):
            return None
        doc = self._collection.find_one({"_id": ObjectId(job_application_id)})
        if not doc:
            return None
        JobApplicationRecord.model_validate(doc)
        out = dict(doc)
        out["id"] = str(out.pop("_id"))
        return out

    def update(self, job_application_id: str, patch: JobApplicationUpdate) -> bool:
        if not ObjectId.is_valid(job_application_id):
            raise ValueError("Invalid job_application_id")
        update: dict[str, Any] = {"updated_at": patch.updated_at or _utcnow()}
        if patch.status is not None:
            update["status"] = patch.status.value
        if patch.source_url is not None:
            update["source_url"] = patch.source_url
        if patch.metadata is not None:
            update["metadata"] = patch.metadata
        res = self._collection.update_one({"_id": ObjectId(job_application_id)}, {"$set": update})
        return bool(res.matched_count)


__all__ = ["JobApplicationService"]
