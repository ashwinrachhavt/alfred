"""Learning agent tools -- spaced repetition and knowledge assessment.

Tools for managing review schedules, assessing knowledge levels using Bloom's
taxonomy, generating quizzes, and Feynman technique checks.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from alfred.core.database import SessionLocal
from alfred.services.zettelkasten_service import ZettelkastenService

logger = logging.getLogger(__name__)


def _get_zettel_service() -> ZettelkastenService:
    """Create a ZettelkastenService with a fresh DB session."""
    session = SessionLocal()
    return ZettelkastenService(session=session)


@tool
def get_due_reviews(limit: int = 50) -> str:
    """Get zettel cards due for spaced repetition review. Returns cards sorted by due date."""
    svc = _get_zettel_service()
    try:
        reviews = svc.list_due_reviews(limit=limit)
        output = []
        for review in reviews:
            card = svc.get_card(review.card_id)
            if card:
                output.append({
                    "review_id": review.id,
                    "card_id": card.id,
                    "title": card.title,
                    "topic": card.topic,
                    "stage": review.stage,
                    "due_at": review.due_at.isoformat() if review.due_at else None,
                    "attempt_count": review.attempt_count,
                })
        return json.dumps(output)
    except Exception as exc:
        logger.error("get_due_reviews failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def submit_review(review_id: int, recalled: bool, confidence: int = 3) -> str:
    """Submit a review result. Recalled: True/False, Confidence: 1-5. Updates next review schedule."""
    svc = _get_zettel_service()
    try:
        review = svc.complete_review(review_id=review_id, recalled=recalled, confidence=confidence)
        if not review:
            return json.dumps({"error": f"Review {review_id} not found"})

        return json.dumps({
            "ok": True,
            "review_id": review_id,
            "recalled": recalled,
            "confidence": confidence,
            "next_stage": review.stage,
            "next_due": review.due_at.isoformat() if review.due_at else None,
        })
    except Exception as exc:
        logger.error("submit_review failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def assess_knowledge(zettel_id: int) -> str:
    """Assess knowledge level for a zettel using Bloom's taxonomy. Returns level and confidence."""
    svc = _get_zettel_service()
    try:
        card = svc.get_card(zettel_id)
        if not card:
            return json.dumps({"error": f"Zettel {zettel_id} not found"})

        # Get review history
        reviews = svc.session.execute(
            "SELECT * FROM zettel_reviews WHERE card_id = :card_id ORDER BY completed_at DESC",
            {"card_id": zettel_id}
        ).fetchall()

        # Compute Bloom's level based on review performance
        # 1: Remember (just encountered)
        # 2: Understand (1-2 successful reviews)
        # 3: Apply (3-5 successful reviews)
        # 4: Analyze (6-10 successful reviews)
        # 5: Evaluate (11-20 successful reviews)
        # 6: Create (20+ successful reviews)

        successful_reviews = sum(1 for r in reviews if r.get("recalled", False))
        avg_confidence = card.confidence if card.confidence else 0.5

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
            "zettel_id": zettel_id,
            "title": card.title,
            "bloom_level": bloom_level,
            "level_name": level_name,
            "successful_reviews": successful_reviews,
            "confidence": avg_confidence,
            "total_reviews": len(reviews),
        })
    except Exception as exc:
        logger.error("assess_knowledge failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def generate_quiz(topic: str | None = None, difficulty: str = "medium", count: int = 5) -> str:
    """Generate quiz questions from zettel cards. Difficulty: easy, medium, hard."""
    svc = _get_zettel_service()
    try:
        # Get cards for the topic
        cards = svc.list_cards(topic=topic, limit=count * 2)
        if not cards:
            return json.dumps({"error": "No cards found for quiz generation"})

        from alfred.core.llm_factory import get_chat_model

        model = get_chat_model()

        # Build context from cards
        card_context = "\n\n".join([
            f"Card {i+1}: {card.title}\n{card.content or card.summary or ''}"
            for i, card in enumerate(cards[:count])
        ])

        system_prompt = (
            f"Generate {count} {difficulty} quiz questions from these knowledge cards. "
            "Return ONLY valid JSON array: [{\"question\": \"...\", \"answer\": \"...\", \"card_id\": N}]"
        )

        response = model.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": card_context},
        ])
        result_text = response.content if hasattr(response, "content") else str(response)

        # Parse JSON
        import re
        json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
        if json_match:
            questions = json.loads(json_match.group())
        else:
            questions = []

        return json.dumps({
            "topic": topic,
            "difficulty": difficulty,
            "questions": questions[:count],
        })
    except Exception as exc:
        logger.error("generate_quiz failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def feynman_check(zettel_id: int, explanation: str) -> str:
    """Check an explanation using Feynman technique. Detects gaps and complexity."""
    svc = _get_zettel_service()
    try:
        card = svc.get_card(zettel_id)
        if not card:
            return json.dumps({"error": f"Zettel {zettel_id} not found"})

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
            f"Original concept: {card.title}\n{card.content or ''}\n\n"
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
            "zettel_id": zettel_id,
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
