from __future__ import annotations

from datetime import datetime, timezone

from alfred.api.company import routes as company_routes
from alfred.models.company import CompanyResearchReportRow
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel


def test_recent_company_research_reports_returns_executive_summary(
    monkeypatch,
) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    SQLModel.metadata.create_all(engine)
    session_local = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    monkeypatch.setattr(company_routes, "SessionLocal", session_local)

    now = datetime.now(timezone.utc)
    with session_local() as session:
        session.add(
            CompanyResearchReportRow(
                company_key="acme",
                company="Acme",
                model_name="test-model",
                generated_at=now,
                updated_at=now,
                payload={"report": {"executive_summary": "Hello"}},
            )
        )
        session.commit()

    results = company_routes.recent_company_research_reports(limit=10)
    assert len(results) == 1
    assert results[0].executive_summary == "Hello"
