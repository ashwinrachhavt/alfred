from __future__ import annotations

from datetime import datetime, timezone

import pytest
from alfred.schemas.interview_prep import InterviewPrepCreate, InterviewPrepRecord
from bson import ObjectId


def test_interview_prep_create_valid():
    payload = InterviewPrepCreate(
        job_application_id=str(ObjectId()),
        company="OpenAI",
        role="AI Engineer",
        interview_date=datetime(2026, 1, 5, tzinfo=timezone.utc),
        interview_type="phone",
    )
    assert payload.company == "OpenAI"
    assert ObjectId.is_valid(str(payload.job_application_id))


def test_interview_prep_record_validation_allows_extra_id():
    record = {
        "_id": ObjectId(),
        "job_application_id": ObjectId(),
        "company": "ExampleCo",
        "role": "Backend Engineer",
        "generated_at": datetime.now(tz=timezone.utc),
        "prep_doc": {"company_overview": "x", "role_analysis": "y"},
        "quiz": {"questions": []},
        "unexpected": {"ok": True},
    }
    parsed = InterviewPrepRecord.model_validate(record)
    assert parsed.company == "ExampleCo"


def test_interview_prep_create_rejects_empty_company():
    with pytest.raises(Exception):
        InterviewPrepCreate(company="  ", role="AI Engineer")
