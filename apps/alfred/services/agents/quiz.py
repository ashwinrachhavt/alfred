"""Quiz schema used by Agno quiz workflows.

Kept small to allow tests to assert validation behavior across changes.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class Quiz(BaseModel):
    topic: str = Field(min_length=1)
    questions: List[str] = Field(min_length=1)


def validate_quiz(data: dict) -> Quiz:
    """Parse and validate a quiz payload."""
    return Quiz.model_validate(data)
