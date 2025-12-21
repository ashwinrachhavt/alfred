from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from alfred.models.learning import LearningReview
from alfred.services.learning_service import LearningService
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_review_scheduling_progression(db_session: Session) -> None:
    svc = LearningService(db_session)
    topic = svc.create_topic(name="DPO")
    svc.add_resource(topic=topic, title="DPO overview", notes="Some notes")

    open_review = db_session.exec(
        select(LearningReview)
        .where(LearningReview.topic_id == topic.id)
        .where(LearningReview.completed_at.is_(None))
    ).first()
    assert open_review is not None
    assert open_review.stage == 1

    # Make it due and complete it
    open_review.due_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.add(open_review)
    db_session.commit()

    completed = svc.complete_review(review=open_review, score=0.9)
    assert completed.completed_at is not None

    next_open = db_session.exec(
        select(LearningReview)
        .where(LearningReview.topic_id == topic.id)
        .where(LearningReview.completed_at.is_(None))
        .order_by(LearningReview.due_at.asc())
    ).first()
    assert next_open is not None
    assert next_open.stage == 2


def test_quiz_fallback_and_attempt_scoring(db_session: Session) -> None:
    svc = LearningService(db_session)
    topic = svc.create_topic(name="Constitutional AI")

    quiz = svc.generate_quiz(topic=topic, question_count=3, source_text="Some study text.")
    assert quiz.id is not None
    assert len(quiz.items) == 3

    known = [True, False, True]
    attempt = svc.submit_quiz(quiz=quiz, known=known, responses=None)
    assert attempt.score == pytest.approx(2 / 3)

    with pytest.raises(ValueError, match="known length must match"):
        svc.submit_quiz(quiz=quiz, known=[True], responses=None)


def test_planner_prioritizes_due_reviews(db_session: Session) -> None:
    svc = LearningService(db_session)
    topic = svc.create_topic(name="RLHF")

    # Create a due review explicitly (no need to wait 1 day)
    db_session.add(
        LearningReview(
            topic_id=topic.id,
            stage=1,
            iteration=1,
            due_at=datetime.utcnow() - timedelta(hours=1),
        )
    )
    db_session.commit()

    items = svc.plan_session(minutes_available=40, include_new_material=True)
    assert items
    assert items[0]["topic_id"] == topic.id
    assert items[0]["review_id"] is not None
