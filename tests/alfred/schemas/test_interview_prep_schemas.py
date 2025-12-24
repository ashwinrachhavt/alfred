from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from alfred.schemas.interview_prep import InterviewPrepCreate, InterviewPrepRecord


def test_interview_prep_create_valid():
    payload = InterviewPrepCreate(
        job_application_id=str(uuid.uuid4()),
        company="OpenAI",
        role="AI Engineer",
        interview_date=datetime(2026, 1, 5, tzinfo=timezone.utc),
        interview_type="phone",
    )
    assert payload.company == "OpenAI"
    uuid.UUID(str(payload.job_application_id))


def test_interview_prep_record_validation_allows_extra_id():
    record = {
        "_id": str(uuid.uuid4()),
        "job_application_id": str(uuid.uuid4()),
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
