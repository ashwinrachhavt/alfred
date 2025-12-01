from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from alfred.services.agents.quiz import Quiz, validate_quiz

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


class QuizPayload(BaseModel):
    topic: str
    questions: list[str]


@router.post("/validate", response_model=Quiz)
def validate(payload: QuizPayload) -> Quiz:
    try:
        return validate_quiz(payload.model_dump())
    except Exception as exc:
        # Normalize validation to HTTP 422
        raise HTTPException(status_code=422, detail=str(exc))
