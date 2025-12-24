from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from alfred.core.settings import settings
from alfred.schemas.interview_prep import (
    InterviewPrepCreate,
    InterviewPrepRecord,
    InterviewPrepUpdate,
)
from alfred.services.mongo import MongoService


def _utcnow() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


@dataclass
class InterviewPrepService:
    """Postgres-backed CRUD and indexing for interview preparation records."""

    database: Any | None = None
    collection_name: str = settings.interview_prep_collection

    def __post_init__(self) -> None:
        if self.database is not None and hasattr(self.database, "get_collection"):
            self._collection = self.database.get_collection(self.collection_name)
        else:
            self._collection = MongoService(default_collection=self.collection_name)

    # -----------------
    # Indexes
    # -----------------
    def ensure_indexes(self) -> None:
        """Create indexes for common interview prep queries (best-effort)."""
        try:
            if hasattr(self._collection, "create_index"):
                self._collection.create_index([("job_application_id", 1)], name="job_app_id")
                self._collection.create_index([("company", 1)], name="company")
                self._collection.create_index([("interview_date", 1)], name="interview_date")
                self._collection.create_index([("generated_at", -1)], name="generated_at_desc")
        except Exception:
            pass

    # -----------------
    # CRUD
    # -----------------
    def create(self, payload: InterviewPrepCreate) -> str:
        """Create a new interview prep record and return its id."""
        now = _utcnow()
        doc = {
            "job_application_id": payload.job_application_id,
            "company": payload.company,
            "role": payload.role,
            "interview_date": payload.interview_date,
            "interview_type": payload.interview_type,
            "source": payload.source,
            "prep_doc": {
                "company_overview": "",
                "role_analysis": "",
                "star_stories": [],
                "likely_questions": [],
                "technical_topics": [],
            },
            "quiz": {"questions": [], "score": None, "attempts": []},
            "performance_rating": None,
            "confidence_rating": None,
            "generated_at": None,
            "created_at": now,
            "updated_at": now,
        }

        return self._collection.insert_one(doc)

    def get(self, interview_prep_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a record by id. Returns a serialized dict or None."""
        doc = self._collection.find_one({"_id": interview_prep_id})
        if not doc:
            return None
        InterviewPrepRecord.model_validate(doc)
        return self._serialize(doc)

    def find_by_interview_date(
        self,
        *,
        start: datetime,
        end: datetime,
        projection: dict[str, Any] | None = None,
        limit: int = 500,
    ) -> list[Dict[str, Any]]:
        """Return records whose `interview_date` is within [start, end]."""
        cursor = self._collection.find(
            {"interview_date": {"$gte": start, "$lte": end}},
            projection=projection,
        ).limit(max(1, min(int(limit), 2000)))
        return list(cursor)

    def update(self, interview_prep_id: str, patch: InterviewPrepUpdate) -> bool:
        """Patch an existing record. Returns True when a document was matched."""
        now = _utcnow()
        update: dict[str, Any] = {"updated_at": now}

        if patch.interview_date is not None:
            update["interview_date"] = patch.interview_date
        if patch.interview_type is not None:
            update["interview_type"] = patch.interview_type
        if patch.prep_doc is not None:
            update["prep_doc"] = patch.prep_doc.model_dump()
        if patch.prep_markdown is not None:
            update["prep_markdown"] = patch.prep_markdown
        if patch.prep_markdown_generated_at is not None:
            update["prep_markdown_generated_at"] = patch.prep_markdown_generated_at
        if patch.quiz is not None:
            update["quiz"] = patch.quiz.model_dump()
        if patch.performance_rating is not None:
            update["performance_rating"] = patch.performance_rating
        if patch.confidence_rating is not None:
            update["confidence_rating"] = patch.confidence_rating
        if patch.generated_at is not None:
            update["generated_at"] = patch.generated_at
        if patch.source is not None:
            update["source"] = patch.source
        if patch.reminders is not None:
            update["reminders"] = patch.reminders.model_dump()
        if patch.checklist is not None:
            update["checklist"] = patch.checklist.model_dump()
        if patch.checklist_generated_at is not None:
            update["checklist_generated_at"] = patch.checklist_generated_at
        if patch.feedback is not None:
            update["feedback"] = patch.feedback.model_dump()
        if patch.calendar_event is not None:
            update["calendar_event"] = patch.calendar_event.model_dump()

        res = self._collection.update_one({"_id": interview_prep_id}, {"$set": update})
        return bool(res.get("matched_count", 0))

    @staticmethod
    def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(doc)
        if "_id" in out:
            out["id"] = str(out.pop("_id"))
        return out


__all__ = ["InterviewPrepService"]
