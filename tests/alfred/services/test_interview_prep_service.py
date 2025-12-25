from __future__ import annotations

from typing import Any

from alfred.schemas.interview_prep import InterviewPrepCreate, InterviewPrepUpdate
from alfred.services.interview_service import InterviewPrepService


class _FakeStore:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def insert_one(self, doc: dict[str, Any]) -> str:  # type: ignore[no-untyped-def]
        _id = str(doc.get("_id") or "id-1")
        doc["_id"] = _id
        self.docs[_id] = dict(doc)
        return _id

    def find_one(self, flt: dict[str, Any]) -> dict[str, Any] | None:  # type: ignore[no-untyped-def]
        _id = flt.get("_id")
        if not _id:
            return None
        return self.docs.get(str(_id))

    def update_one(self, flt: dict[str, Any], update: dict[str, Any]):  # type: ignore[no-untyped-def]
        _id = str(flt.get("_id"))
        if _id not in self.docs:
            return {"matched_count": 0}
        patch = (update.get("$set") or {}) if isinstance(update, dict) else {}
        self.docs[_id].update(patch)
        return {"matched_count": 1}


def test_interview_prep_crud_roundtrip_without_db() -> None:
    store = _FakeStore()
    svc = InterviewPrepService(collection_name="interview_preps", store=store)  # type: ignore[arg-type]

    interview_id = svc.create(InterviewPrepCreate(company="Acme", role="Backend Engineer"))
    got = svc.get(interview_id)
    assert got and got["company"] == "Acme"

    ok = svc.update(interview_id, InterviewPrepUpdate(interview_type="phone_screen"))
    assert ok is True
    got2 = svc.get(interview_id)
    assert got2 and got2["interview_type"] == "phone_screen"
