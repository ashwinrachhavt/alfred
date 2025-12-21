from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from alfred.core.dependencies import get_llm_service
from alfred.prompts import load_prompt
from alfred.schemas.interview_prep import InterviewQuiz, PrepDoc

SYSTEM_PROMPT = load_prompt("interview_prep", "system.md")
QUIZ_PROMPT = load_prompt("interview_prep", "quiz.md")


def _safe_json(obj: Any, *, max_chars: int) -> str:
    try:
        text = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        text = str(obj)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n…"


@dataclass
class InterviewQuizGenerator:
    """Generate a practice quiz tailored to an interview prep doc."""

    llm: Any = None

    def __post_init__(self) -> None:
        if self.llm is None:
            self.llm = get_llm_service()

    def generate_quiz(
        self,
        *,
        company: str,
        role: str,
        prep_doc: PrepDoc,
        num_questions: int = 12,
    ) -> InterviewQuiz:
        company = (company or "").strip()
        role = (role or "").strip()
        if not company:
            raise ValueError("company is required")
        if not role:
            raise ValueError("role is required")

        user_prompt = QUIZ_PROMPT.format(
            company=company,
            role=role,
            num_questions=max(5, min(int(num_questions), 25)),
            prep_doc=_safe_json(prep_doc.model_dump(), max_chars=16_000),
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        try:
            return self.llm.structured(messages=messages, schema=InterviewQuiz)
        except Exception:
            raw = self.llm.chat(messages=messages)
            try:
                return InterviewQuiz.model_validate_json(raw)
            except Exception as exc:
                raise ValueError("Failed to parse InterviewQuiz JSON from model output") from exc


__all__ = ["InterviewQuizGenerator"]
