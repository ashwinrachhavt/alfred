"""Tests for POST /api/zettels/cards/{id}/resume-enrichment (T7)."""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from alfred.api.dependencies import get_db_session
from alfred.api.zettels.routes import router as zettels_router
from alfred.core.utils import utcnow_naive
from alfred.models.zettel import ZettelCard
from alfred.services.zettelkasten_service import ZettelkastenService


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(zettels_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    return TestClient(app)


def _make_card(
    db_session: Session,
    *,
    bloom_source: str = "backfill",
    enrichment_attempted_at=None,
    enrichment_last_error: str | None = None,
) -> ZettelCard:
    svc = ZettelkastenService(db_session)
    # Stub ensure_embedding so we don't hit OpenAI/Qdrant during fixture setup.
    svc.ensure_embedding = MagicMock(side_effect=lambda card: card)  # type: ignore[method-assign]
    card = svc.create_card(
        title="A knowledge card",
        content="The CAP theorem says you can have two of consistency, availability, partition tolerance.",
        bloom_source=bloom_source,
    )
    # Mutate in place to reach the target fixture state; this is test setup,
    # not production persistence (no updated_at concern here).
    if enrichment_attempted_at is not None:
        card.enrichment_attempted_at = enrichment_attempted_at
    if enrichment_last_error is not None:
        card.enrichment_last_error = enrichment_last_error
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    return card


def _mock_llm_response(data: dict) -> MagicMock:
    llm = MagicMock()
    response = MagicMock()
    response.content = json.dumps(data)
    llm.invoke = MagicMock(return_value=response)
    return llm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_resume_enrichment_runs_on_never_attempted_card(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    card = _make_card(db_session)
    assert card.enrichment_attempted_at is None
    assert card.bloom_source == "backfill"
    assert card.bloom_level == 1

    fake_llm = _mock_llm_response(
        {
            "enrichment": {
                "summary": "A pithy one-liner.",
                "suggested_tags": ["distributed", "cap"],
                "suggested_topic": "distributed-systems",
            },
            "bloom_assessment": {
                "inferred_level": 4,
                "rationale": "requires decomposition of tradeoffs",
                "evidence_phrases": ["two of three"],
            },
        }
    )
    monkeypatch.setattr(
        "alfred.services.enrichment_service.get_chat_model",
        lambda **kwargs: fake_llm,
    )

    resp = client.post(f"/api/zettels/cards/{card.id}/resume-enrichment")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "complete"
    assert body["card_id"] == card.id
    assert body["bloom_level"] == 4

    db_session.expire_all()
    refreshed = db_session.get(ZettelCard, card.id)
    assert refreshed is not None
    assert refreshed.bloom_level == 4
    assert refreshed.bloom_source == "ai_inferred"
    assert refreshed.enrichment_attempted_at is not None
    assert refreshed.enrichment_last_error is None
    assert refreshed.summary == "A pithy one-liner."
    assert refreshed.topic == "distributed-systems"
    assert refreshed.tags == ["distributed", "cap"]
    # Bloom history has a new entry
    assert refreshed.bloom_history is not None
    assert len(refreshed.bloom_history) == 1
    assert refreshed.bloom_history[0]["level"] == 4
    assert refreshed.bloom_history[0]["source"] == "ai_inferred"


def test_resume_enrichment_is_idempotent_on_success(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Already-enriched card must return already_complete WITHOUT calling LLM."""
    card = _make_card(
        db_session,
        bloom_source="ai_inferred",
        enrichment_attempted_at=utcnow_naive(),
        enrichment_last_error=None,
    )

    # If the service tries to call this, the test fails.
    def _should_not_call(**_kwargs):  # pragma: no cover - ensures no call
        raise AssertionError("LLM must not be called for already-complete cards")

    monkeypatch.setattr(
        "alfred.services.enrichment_service.get_chat_model",
        _should_not_call,
    )

    resp = client.post(f"/api/zettels/cards/{card.id}/resume-enrichment")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "already_complete"
    assert body["card_id"] == card.id


def test_resume_enrichment_retries_on_prior_failure(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    card = _make_card(
        db_session,
        enrichment_attempted_at=utcnow_naive(),
        enrichment_last_error="earlier error",
    )

    fake_llm = _mock_llm_response(
        {
            "enrichment": {
                "summary": "retry worked",
                "suggested_tags": ["ok"],
            },
            "bloom_assessment": {
                "inferred_level": 2,
                "rationale": "definition",
                "evidence_phrases": [],
            },
        }
    )
    monkeypatch.setattr(
        "alfred.services.enrichment_service.get_chat_model",
        lambda **kwargs: fake_llm,
    )

    resp = client.post(f"/api/zettels/cards/{card.id}/resume-enrichment")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "complete"

    db_session.expire_all()
    refreshed = db_session.get(ZettelCard, card.id)
    assert refreshed is not None
    assert refreshed.enrichment_last_error is None
    assert refreshed.summary == "retry worked"


def test_resume_enrichment_records_failure(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    card = _make_card(db_session)

    def _boom(**_kwargs):
        llm = MagicMock()
        llm.invoke = MagicMock(side_effect=RuntimeError("openai 429 rate limit"))
        return llm

    monkeypatch.setattr(
        "alfred.services.enrichment_service.get_chat_model",
        _boom,
    )

    resp = client.post(f"/api/zettels/cards/{card.id}/resume-enrichment")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert "openai 429 rate limit" in body["error"]

    db_session.expire_all()
    refreshed = db_session.get(ZettelCard, card.id)
    assert refreshed is not None
    assert refreshed.enrichment_attempted_at is not None
    assert refreshed.enrichment_last_error is not None
    assert "openai 429 rate limit" in refreshed.enrichment_last_error
    # Bloom fields remained untouched on failure.
    assert refreshed.bloom_source == "backfill"
    assert refreshed.bloom_level == 1


def test_resume_enrichment_404_on_missing_card(client: TestClient) -> None:
    resp = client.post("/api/zettels/cards/99999/resume-enrichment")
    assert resp.status_code == 404


def test_resume_enrichment_does_not_mutate_updated_at(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Iron-rule regression: resume-enrichment is infrastructure metadata,
    NOT a user edit, so updated_at must not be bumped."""
    card = _make_card(db_session)
    # Pin updated_at to a known past value so we can spot any bump.
    pinned = utcnow_naive() - timedelta(days=3)
    card.updated_at = pinned
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    baseline_updated_at = card.updated_at

    fake_llm = _mock_llm_response(
        {
            "enrichment": {"summary": "s"},
            "bloom_assessment": {
                "inferred_level": 3,
                "rationale": "r",
                "evidence_phrases": [],
            },
        }
    )
    monkeypatch.setattr(
        "alfred.services.enrichment_service.get_chat_model",
        lambda **kwargs: fake_llm,
    )

    resp = client.post(f"/api/zettels/cards/{card.id}/resume-enrichment")
    assert resp.status_code == 200
    assert resp.json()["status"] == "complete"

    db_session.expire_all()
    refreshed = db_session.get(ZettelCard, card.id)
    assert refreshed is not None
    assert (
        refreshed.updated_at == baseline_updated_at
    ), f"updated_at was mutated: {refreshed.updated_at} != {baseline_updated_at}"
