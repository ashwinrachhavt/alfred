from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from alfred.schemas.interview_prep import InterviewPrepCreate, InterviewPrepUpdate
from alfred.services.interview_prep import InterviewPrepService
from bson import ObjectId
from pymongo import MongoClient


def _connect_client() -> MongoClient | None:
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    try:
        client = MongoClient(
            uri,
            uuidRepresentation="standard",
            serverSelectionTimeoutMS=200,
            connectTimeoutMS=200,
            socketTimeoutMS=200,
        )
        client.admin.command("ping")
        return client
    except Exception:
        return None


@pytest.mark.integration
def test_interview_prep_insert_get_update_roundtrip():
    client = _connect_client()
    if client is None:
        pytest.skip("MongoDB not available for integration test")

    dbname = "notes_db_test_interview_prep"
    db = client[dbname]
    try:
        svc = InterviewPrepService(database=db, collection_name="interview_preps")
        svc.ensure_indexes()

        job_app_id = ObjectId()
        prep_id = svc.create(
            InterviewPrepCreate(
                job_application_id=job_app_id,
                company="ExampleCo",
                role="Backend Engineer",
                interview_date=datetime(2026, 1, 5, tzinfo=timezone.utc),
                interview_type="onsite",
            )
        )
        assert ObjectId.is_valid(prep_id)

        fetched = svc.get(prep_id)
        assert fetched is not None
        assert fetched["company"] == "ExampleCo"
        assert fetched["job_application_id"] == str(job_app_id)

        ok = svc.update(
            prep_id,
            InterviewPrepUpdate(
                performance_rating=8,
                confidence_rating=7,
                generated_at=datetime.now(tz=timezone.utc),
            ),
        )
        assert ok is True
        fetched2 = svc.get(prep_id)
        assert fetched2 is not None
        assert fetched2["performance_rating"] == 8
    finally:
        client.drop_database(dbname)
