from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from alfred.pipeline.cache import PipelineStageCache


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_cache_miss(db_session: Session):
    cache = PipelineStageCache(session=db_session)
    result = cache.get("extract", "abc123")
    assert result is None


def test_cache_set_and_hit(db_session: Session):
    cache = PipelineStageCache(session=db_session)
    data = {"summary": {"short": "test"}, "topics": {}}
    cache.set("extract", "abc123", data)
    result = cache.get("extract", "abc123")
    assert result == data


def test_cache_overwrite(db_session: Session):
    cache = PipelineStageCache(session=db_session)
    cache.set("extract", "abc123", {"v": 1})
    cache.set("extract", "abc123", {"v": 2})
    assert cache.get("extract", "abc123") == {"v": 2}


def test_cache_different_stages(db_session: Session):
    cache = PipelineStageCache(session=db_session)
    cache.set("extract", "abc123", {"stage": "extract"})
    cache.set("classify", "abc123", {"stage": "classify"})
    assert cache.get("extract", "abc123")["stage"] == "extract"
    assert cache.get("classify", "abc123")["stage"] == "classify"
