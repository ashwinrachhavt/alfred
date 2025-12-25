"""Job hunt feature service facade.

This module provides a single import path for job-hunt workflows by composing
application tracking, company research, and outreach services.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from alfred.core.settings import settings
from alfred.core.utils import utcnow as _utcnow
from alfred.schemas.job_applications import (
    JobApplicationCreate,
    JobApplicationRecord,
    JobApplicationStatus,
    JobApplicationUpdate,
)
from alfred.services.datastore import DataStoreService


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


@dataclass(slots=True)
class JobHuntService:
    """Feature-level facade for job search workflows."""

    applications: Any | None = None
    company_research: Any | None = None

    def _applications(self):
        if self.applications is None:
            self.applications = JobApplicationService()
        return self.applications

    def _company_research(self):
        if self.company_research is None:
            from alfred.core.dependencies import get_company_research_service

            self.company_research = get_company_research_service()
        return self.company_research

    def create_application(self, payload):
        """Create a job application record.

        Payload should be a `JobApplicationCreate` instance.
        """

        return self._applications().create(payload)

    def update_application(self, job_application_id: str, patch):
        """Update a job application record.

        Patch should be a `JobApplicationUpdate` instance.
        """

        return self._applications().update(job_application_id, patch)

    def company_report(self, company: str):
        """Generate or fetch a company research report."""

        return self._company_research().generate_report(company)

    def outreach_kit(self, company: str, role: str = "AI Engineer", *, personal_context: str = ""):
        """Generate an outreach kit for a company and role."""

        from alfred.services.company_outreach_service import generate_company_outreach

        return generate_company_outreach(company, role=role, personal_context=personal_context)


__all__ = ["JobApplicationService", "JobHuntService"]
