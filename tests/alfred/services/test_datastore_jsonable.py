from __future__ import annotations

from datetime import datetime

from alfred.models.datastore import DataStoreRow
from alfred.services.datastore import DataStoreService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session


def test_datastore_serializes_datetime_values(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    DataStoreRow.__table__.create(engine)
    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    monkeypatch.setattr("alfred.services.datastore.SessionLocal", session_local)

    svc = DataStoreService(default_collection="__test_datastore_jsonable")
    doc_id = svc.insert_one({"created_at": datetime(2025, 1, 1, 12, 0, 0)})
    stored = svc.find_one({"_id": doc_id})
    assert stored is not None
    assert stored["created_at"] == "2025-01-01T12:00:00"
