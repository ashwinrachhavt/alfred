from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from alfred.core.settings import settings
from alfred.schemas.culture_fit import (
    CultureFitProfileRecord,
    CultureFitProfileUpsert,
    UserValuesProfile,
)
from alfred.services.mongo import MongoService


def _utcnow() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


@dataclass
class CultureFitProfileService:
    """Postgres-backed storage for user culture-fit preference profiles."""

    collection_name: str = settings.culture_fit_profiles_collection

    def __post_init__(self) -> None:
        self._collection = MongoService(default_collection=self.collection_name)

    # -----------------
    # Indexes
    # -----------------
    def ensure_indexes(self) -> None:
        """Create best-effort indexes for profile lookup."""
        try:
            self._collection.create_index([("user_id", 1)], name="user_id", unique=True)
            self._collection.create_index([("updated_at", -1)], name="updated_at_desc")
        except Exception:
            pass

    # -----------------
    # CRUD
    # -----------------
    def upsert(self, payload: CultureFitProfileUpsert) -> str:
        """Create or update a profile; returns record id."""
        user_id = (payload.user_id or "").strip() or "default"
        now = _utcnow()

        profile = UserValuesProfile(
            values={"dimensions": payload.values},
            notes=payload.notes,
        )

        update: dict[str, Any] = {
            "user_id": user_id,
            "profile": profile.model_dump(mode="json"),
            "updated_at": now,
        }
        existing = self._collection.find_one({"user_id": user_id})
        if existing:
            self._collection.update_one({"user_id": user_id}, {"$set": update})
            return str(existing.get("_id") or user_id)

        doc = dict(update)
        doc["created_at"] = now
        res = self._collection.insert_one(doc)
        return str(res.inserted_id)

    def get_by_user_id(self, user_id: str | None) -> Optional[Dict[str, Any]]:
        uid = (user_id or "").strip() or "default"
        doc = self._collection.find_one({"user_id": uid})
        if not doc:
            return None
        record = self._serialize(doc)
        CultureFitProfileRecord.model_validate(record)
        return record

    @staticmethod
    def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(doc)
        if "_id" in out:
            out["id"] = str(out.pop("_id"))
        return out


__all__ = ["CultureFitProfileService"]
