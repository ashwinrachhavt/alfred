from __future__ import annotations

from datetime import datetime, timezone

import pytest
from alfred.models.company import CompanyResearchReportRow
from alfred.services.company_research_service import CompanyResearchService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session


@pytest.mark.usefixtures("_disable_network")
def test_company_research_service_db_roundtrip(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    CompanyResearchReportRow.__table__.create(engine)

    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    monkeypatch.setattr("alfred.services.company_research_service.SessionLocal", session_local)

    svc = CompanyResearchService(store=None)

    payload = {
        "company": "Mercury",
        "model": "test-model",
        "generated_at": "2026-01-05T00:00:00+00:00",
        "report": {"executive_summary": "hello"},
    }

    stored = svc._upsert_latest_to_db(
        company="Mercury",
        payload=payload,
        model_name="test-model",
        generated_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
    )
    assert stored["company"] == "Mercury"
    assert "id" in stored

    fetched = svc._read_latest_from_db("mercury")
    assert fetched is not None
    assert fetched["id"] == stored["id"]
    assert fetched["report"]["executive_summary"] == "hello"

