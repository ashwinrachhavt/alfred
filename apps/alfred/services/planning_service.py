from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import BaseModel, Field

from alfred.core.settings import LLMProvider, settings
from alfred.core.utils import clamp_int
from alfred.schemas.intelligence import ExecutionPlan, PlanStep
from alfred.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class _PlanDraft(BaseModel):
    steps: list[str] = Field(default_factory=list)


def _normalize_steps(steps: list[str], *, max_steps: int) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in steps or []:
        step = " ".join((raw or "").strip().split())
        if not step:
            continue
        key = step.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(step)
        if len(cleaned) >= max_steps:
            break
    return cleaned


@dataclass(slots=True)
class PlanningService:
    """Generate compact, executable plans for complex problem solving."""

    llm_service: LLMService | None = None

    def _llm(self) -> LLMService:
        return self.llm_service or LLMService()

    def create_plan(
        self, *, goal: str, context: str | None = None, max_steps: int = 6
    ) -> ExecutionPlan:
        goal_norm = " ".join((goal or "").strip().split())
        if not goal_norm:
            raise ValueError("goal is required")
        max_steps = clamp_int(int(max_steps), lo=1, hi=12)

        steps = self._try_llm_plan(goal=goal_norm, context=context, max_steps=max_steps)
        if not steps:
            steps = self._heuristic_plan(goal=goal_norm, max_steps=max_steps)

        steps = _normalize_steps(steps, max_steps=max_steps)
        if not steps:
            steps = [
                "Clarify requirements and constraints",
                "Implement the solution",
                "Validate and document",
            ]

        return ExecutionPlan(
            goal=goal_norm,
            steps=[PlanStep(step=s, status="pending") for s in steps],
        )

    def _try_llm_plan(self, *, goal: str, context: str | None, max_steps: int) -> list[str] | None:
        if settings.llm_provider != LLMProvider.openai:
            return None

        api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        if not api_key and not settings.openai_base_url:
            return None

        sys = (
            "You generate execution plans for an AI assistant.\n"
            "Return JSON only.\n"
            f"Constraints:\n- Max {max_steps} steps\n"
            "- Each step must be a single action, phrased as an imperative\n"
            "- Steps must be independently verifiable\n"
            "- Do not include sub-bullets or explanations\n"
            "- Do not mention internal tooling\n"
        )

        user_parts = [f"Goal: {goal}"]
        if context:
            ctx = (context or "").strip()
            if ctx:
                user_parts.append(f"Context: {ctx}")

        try:
            draft = self._llm().structured(
                [
                    {"role": "system", "content": sys},
                    {"role": "user", "content": "\n".join(user_parts)},
                ],
                schema=_PlanDraft,
                model=settings.llm_model,
            )
            steps = _normalize_steps(list(draft.steps or []), max_steps=max_steps)
            return steps
        except Exception as exc:  # pragma: no cover - network/provider dependent
            logger.debug("LLM plan generation failed; falling back: %s", exc)
            return None

    @staticmethod
    def _heuristic_plan(*, goal: str, max_steps: int) -> list[str]:
        base = [
            "Clarify requirements and constraints",
            "Gather required context and inputs",
            "Design the approach and data flow",
            "Implement the core functionality",
            "Add validation and error handling",
            "Verify with targeted checks and document usage",
        ]
        if max_steps <= 3:
            return [
                "Clarify requirements and constraints",
                "Implement the core functionality",
                "Verify with targeted checks and document usage",
            ][:max_steps]
        return base[:max_steps]


__all__ = ["PlanningService"]
