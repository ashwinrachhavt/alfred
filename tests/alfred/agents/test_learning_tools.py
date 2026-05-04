from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from alfred.agents.tools import learning_tools


class FakeSession:
    def __init__(self) -> None:
        self.closed = False
        self.topics = {
            5: SimpleNamespace(id=5, name="Retrieval Practice"),
        }
        self.reviews = {
            7: SimpleNamespace(
                id=7,
                topic_id=5,
                stage=1,
                iteration=1,
                due_at=datetime(2026, 4, 12, 12, 0, 0),
                completed_at=None,
                score=None,
            )
        }

    def get(self, model: object, object_id: int) -> SimpleNamespace | None:
        model_name = getattr(model, "__name__", "")
        if model_name == "LearningTopic":
            return self.topics.get(object_id)
        if model_name == "LearningReview":
            return self.reviews.get(object_id)
        return None

    def exec(self, stmt: object) -> SimpleNamespace:
        return SimpleNamespace(first=lambda: None)

    def close(self) -> None:
        self.closed = True


class BombZettelService:
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("learning tools must not use ZettelkastenService")


def test_get_due_reviews_uses_learning_service(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()

    class FakeLearningService:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        def list_due_reviews(self, *, limit: int) -> list[SimpleNamespace]:
            assert limit == 10
            return list(self.session.reviews.values())

    monkeypatch.setattr(learning_tools, "SessionLocal", lambda: session)
    monkeypatch.setattr(learning_tools, "LearningService", FakeLearningService, raising=False)
    monkeypatch.setattr(learning_tools, "ZettelkastenService", BombZettelService, raising=False)

    result = json.loads(learning_tools.get_due_reviews.invoke({"limit": 10}))

    assert session.closed is True
    assert result == [
        {
            "review_id": 7,
            "topic_id": 5,
            "topic_name": "Retrieval Practice",
            "stage": 1,
            "iteration": 1,
            "due_at": "2026-04-12T12:00:00",
            "score": None,
        }
    ]


def test_submit_review_accepts_score_and_uses_learning_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    seen: dict[str, object] = {}

    class FakeLearningService:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        def complete_review(
            self,
            *,
            review: SimpleNamespace,
            score: float | None,
            attempt_id: int | None = None,
        ) -> SimpleNamespace:
            seen["review"] = review
            seen["score"] = score
            seen["attempt_id"] = attempt_id
            return SimpleNamespace(
                id=review.id,
                topic_id=review.topic_id,
                stage=2,
                iteration=review.iteration,
                due_at=datetime(2026, 4, 19, 12, 0, 0),
                completed_at=datetime(2026, 4, 12, 12, 5, 0),
                score=score,
            )

    monkeypatch.setattr(learning_tools, "SessionLocal", lambda: session)
    monkeypatch.setattr(learning_tools, "LearningService", FakeLearningService, raising=False)
    monkeypatch.setattr(learning_tools, "ZettelkastenService", BombZettelService, raising=False)

    result = json.loads(learning_tools.submit_review.invoke({"review_id": 7, "score": 1.0}))

    assert session.closed is True
    assert seen["review"] is session.reviews[7]
    assert seen["score"] == 1.0
    assert seen["attempt_id"] is None
    assert result["ok"] is True
    assert result["review_id"] == 7
    assert result["topic_id"] == 5
    assert result["score"] == 1.0
    assert result["next_stage"] == 2
    assert result["next_due"] == "2026-04-19T12:00:00"


def test_submit_review_maps_legacy_recalled_confidence_to_passing_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    seen: dict[str, object] = {}

    class FakeLearningService:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        def complete_review(
            self,
            *,
            review: SimpleNamespace,
            score: float | None,
            attempt_id: int | None = None,
        ) -> SimpleNamespace:
            seen["score"] = score
            return SimpleNamespace(
                id=review.id,
                topic_id=review.topic_id,
                stage=2,
                iteration=review.iteration,
                due_at=datetime(2026, 4, 19, 12, 0, 0),
                completed_at=datetime(2026, 4, 12, 12, 5, 0),
                score=score,
            )

    monkeypatch.setattr(learning_tools, "SessionLocal", lambda: session)
    monkeypatch.setattr(learning_tools, "LearningService", FakeLearningService, raising=False)
    monkeypatch.setattr(learning_tools, "ZettelkastenService", BombZettelService, raising=False)

    result = json.loads(
        learning_tools.submit_review.invoke(
            {"review_id": 7, "recalled": True, "confidence": 3}
        )
    )

    assert seen["score"] == 0.9
    assert result["ok"] is True
    assert result["score"] == 0.9
