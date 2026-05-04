"""Learning agent tools -- spaced repetition and knowledge assessment.

Tools for managing review schedules, assessing knowledge levels using Bloom's
taxonomy, generating quizzes, and Feynman technique checks.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from langchain_core.tools import tool
from sqlmodel import Session, select

from alfred.core.database import SessionLocal
from alfred.models.learning import LearningReview, LearningTopic
from alfred.services.learning_service import LearningService

logger = logging.getLogger(__name__)


@contextmanager
def _learning_context() -> Iterator[tuple[LearningService, Session]]:
    """Create a LearningService with a fresh DB session and close it."""
    session = SessionLocal()
    try:
        yield LearningService(session=session), session
    finally:
        session.close()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _score_from_review_input(
    *,
    score: float | None,
    recalled: bool | None,
    confidence: int,
) -> float:
    if score is not None:
        return max(0.0, min(1.0, float(score)))

    if recalled is None:
        raise ValueError("Either score or recalled must be provided")

    if not recalled:
        return 0.0

    # Backward compatibility for the original agent tool contract:
    # recalled=True should be treated as a passing review, with confidence
    # adjusting how strong that pass is.
    confidence = max(1, min(5, int(confidence)))
    return {1: 0.8, 2: 0.85, 3: 0.9, 4: 0.95, 5: 1.0}[confidence]


def _next_open_review(session: Session, *, topic_id: int) -> LearningReview | None:
    stmt = (
        select(LearningReview)
        .where(LearningReview.topic_id == topic_id)
        .where(LearningReview.completed_at.is_(None))
        .order_by(LearningReview.due_at.asc())
    )
    return session.exec(stmt).first()


def _find_topic(
    session: Session,
    *,
    topic_id: int | None = None,
    topic_name: str | None = None,
) -> LearningTopic | None:
    if topic_id is not None:
        return session.get(LearningTopic, topic_id)

    name = (topic_name or "").strip()
    if not name:
        return None

    stmt = select(LearningTopic).where(LearningTopic.name == name)
    exact = session.exec(stmt).first()
    if exact:
        return exact

    candidates = list(session.exec(select(LearningTopic)))
    lowered = name.lower()
    return next((topic for topic in candidates if topic.name.lower() == lowered), None)


def _review_payload(review: LearningReview, topic: LearningTopic | None) -> dict:
    return {
        "review_id": review.id,
        "topic_id": review.topic_id,
        "topic_name": topic.name if topic else "Unknown Topic",
        "stage": int(review.stage),
        "iteration": int(review.iteration),
        "due_at": _iso(review.due_at),
        "score": review.score,
    }


@tool
def get_due_reviews(limit: int = 50) -> str:
    """Get learning topics due for spaced repetition review. Returns reviews sorted by due date."""
    try:
        with _learning_context() as (svc, session):
            reviews = svc.list_due_reviews(limit=limit)
            topic_ids = {review.topic_id for review in reviews}
            topics = {
                topic.id: topic
                for topic in (
                    session.get(LearningTopic, topic_id) for topic_id in topic_ids
                )
                if topic and topic.id is not None
            }

        output = []
        for review in reviews:
            output.append(_review_payload(review, topics.get(review.topic_id)))
        return json.dumps(output)
    except Exception as exc:
        logger.error("get_due_reviews failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def submit_review(
    review_id: int,
    recalled: bool | None = None,
    confidence: int = 3,
    score: float | None = None,
    attempt_id: int | None = None,
) -> str:
    """Submit a learning review result. Pass score 0-1, or recalled plus confidence 1-5."""
    try:
        review_score = _score_from_review_input(
            score=score,
            recalled=recalled,
            confidence=confidence,
        )
        with _learning_context() as (svc, session):
            review = session.get(LearningReview, review_id)
            if not review:
                return json.dumps({"error": f"Review {review_id} not found"})

            completed = svc.complete_review(
                review=review,
                score=review_score,
                attempt_id=attempt_id,
            )
            next_review = _next_open_review(session, topic_id=completed.topic_id)
            schedule = next_review or completed

        if not completed:
            return json.dumps({"error": f"Review {review_id} not found"})

        return json.dumps({
            "ok": True,
            "review_id": review_id,
            "topic_id": completed.topic_id,
            "score": review_score,
            "recalled": recalled,
            "confidence": confidence,
            "completed_at": _iso(completed.completed_at),
            "next_stage": int(schedule.stage),
            "next_iteration": int(schedule.iteration),
            "next_due": _iso(schedule.due_at),
        })
    except Exception as exc:
        logger.error("submit_review failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def assess_knowledge(topic_id: int | None = None, zettel_id: int | None = None) -> str:
    """Assess knowledge level for a learning topic using review performance."""
    try:
        effective_topic_id = topic_id if topic_id is not None else zettel_id
        if effective_topic_id is None:
            return json.dumps({"error": "topic_id is required"})

        with _learning_context() as (_svc, session):
            topic = session.get(LearningTopic, effective_topic_id)
            if not topic:
                return json.dumps({"error": f"Topic {effective_topic_id} not found"})

            stmt = (
                select(LearningReview)
                .where(LearningReview.topic_id == effective_topic_id)
                .where(LearningReview.completed_at.is_not(None))
                .order_by(LearningReview.completed_at.desc())
            )
            reviews = list(session.exec(stmt))
            next_review = _next_open_review(session, topic_id=effective_topic_id)

        scores = [float(review.score) for review in reviews if review.score is not None]
        successful_reviews = sum(1 for score_value in scores if score_value >= 0.8)
        average_score = float(sum(scores) / len(scores)) if scores else 0.0

        if successful_reviews == 0:
            bloom_level = 1
            level_name = "Remember"
        elif successful_reviews <= 2:
            bloom_level = 2
            level_name = "Understand"
        elif successful_reviews <= 5:
            bloom_level = 3
            level_name = "Apply"
        elif successful_reviews <= 10:
            bloom_level = 4
            level_name = "Analyze"
        elif successful_reviews <= 20:
            bloom_level = 5
            level_name = "Evaluate"
        else:
            bloom_level = 6
            level_name = "Create"

        return json.dumps({
            "topic_id": effective_topic_id,
            "topic_name": topic.name,
            "bloom_level": bloom_level,
            "level_name": level_name,
            "successful_reviews": successful_reviews,
            "average_score": average_score,
            "total_reviews": len(reviews),
            "next_review_due_at": _iso(next_review.due_at) if next_review else None,
            "next_review_stage": int(next_review.stage) if next_review else None,
        })
    except Exception as exc:
        logger.error("assess_knowledge failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def generate_quiz(
    topic_id: int | None = None,
    topic: str | None = None,
    difficulty: str = "medium",
    count: int = 5,
) -> str:
    """Generate quiz questions for a learning topic. Difficulty is advisory metadata."""
    try:
        with _learning_context() as (svc, session):
            learning_topic = _find_topic(session, topic_id=topic_id, topic_name=topic)
            if not learning_topic:
                identifier = topic_id if topic_id is not None else topic
                return json.dumps({"error": f"Topic {identifier} not found"})

            quiz = svc.generate_quiz(
                topic=learning_topic,
                question_count=count,
            )
            questions = [
                {
                    "question": item.get("question"),
                    "answer": item.get("answer"),
                }
                for item in quiz.items
                if item.get("question")
            ]

        return json.dumps({
            "topic_id": learning_topic.id,
            "topic": learning_topic.name,
            "difficulty": difficulty,
            "quiz_id": quiz.id,
            "questions": questions[:count],
        })
    except Exception as exc:
        logger.error("generate_quiz failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def feynman_check(
    explanation: str,
    topic_id: int | None = None,
    topic: str | None = None,
    zettel_id: int | None = None,
) -> str:
    """Check a learning-topic explanation using the Feynman technique."""
    try:
        effective_topic_id = topic_id if topic_id is not None else zettel_id
        with _learning_context() as (svc, session):
            learning_topic = _find_topic(
                session,
                topic_id=effective_topic_id,
                topic_name=topic,
            )
            if not learning_topic:
                identifier = effective_topic_id if effective_topic_id is not None else topic
                return json.dumps({"error": f"Topic {identifier} not found"})

            resources = svc.list_resources(topic_id=learning_topic.id or 0)
            resource_context = "\n".join(
                f"- {resource.title or 'Untitled'}: {resource.notes or ''}"
                for resource in resources[:5]
            )

        from alfred.core.llm_factory import get_chat_model

        model = get_chat_model()

        system_prompt = (
            "You are a Feynman technique coach. Analyze this explanation for:\n"
            "1. Gaps in understanding (missing key concepts)\n"
            "2. Unnecessary jargon or complexity\n"
            "3. Clarity and simplicity\n"
            "Return JSON: {\"gaps\": [...], \"jargon\": [...], \"clarity_score\": 0.8, \"feedback\": \"...\"}"
        )

        user_prompt = (
            f"Learning topic: {learning_topic.name}\n"
            f"Description: {learning_topic.description or ''}\n"
            f"Resources:\n{resource_context}\n\n"
            f"User's explanation: {explanation}"
        )

        response = model.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        result_text = response.content if hasattr(response, "content") else str(response)

        # Parse JSON
        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group())
        else:
            analysis = {"error": "Failed to parse analysis"}

        return json.dumps({
            "topic_id": learning_topic.id,
            "topic": learning_topic.name,
            "analysis": analysis,
        })
    except Exception as exc:
        logger.error("feynman_check failed: %s", exc)
        return json.dumps({"error": str(exc)})


# List of all learning tools for agent registration
LEARNING_TOOLS = [
    get_due_reviews,
    submit_review,
    assess_knowledge,
    generate_quiz,
    feynman_check,
]
