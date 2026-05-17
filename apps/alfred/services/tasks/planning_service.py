"""AI task planner ported from Neuralflow's todoAgent."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session

from alfred.core.llm_factory import get_chat_model
from alfred.models.tasks import TaskPriority
from alfred.schemas.tasks import PlannedTask, TaskPlanResponse, TaskResponse
from alfred.services.tasks.exceptions import (
    TaskPlanningParseError,
    TaskPlanningUnavailableError,
    TaskValidationError,
)
from alfred.services.tasks.learning_service import TaskLearningService
from alfred.services.tasks.task_service import TaskService

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")
MAX_PLANNER_INPUT_CHARS = 12_000
MAX_PLANNED_TASKS = 25
_REFUSAL_MARKERS = (
    "i can't",
    "i cannot",
    "i’m unable",
    "i am unable",
    "i won't",
    "i will not",
    "cannot comply",
)


class _PlannerTask(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    description_md: str | None = None
    estimatePomodoros: int | None = Field(default=None, ge=1, le=12)
    estimated_pomodoros: int | None = Field(default=None, ge=1, le=12)
    priority: TaskPriority = TaskPriority.MEDIUM
    tags: list[str] = Field(default_factory=list)


class _PlannerOutput(BaseModel):
    tasks: list[_PlannerTask] = Field(default_factory=list)
    rationale: str | None = None


@dataclass(slots=True)
class TaskPlanningService:
    session: Session

    def plan(
        self,
        *,
        user_id: str,
        input_text: str,
        create_tasks: bool = False,
        board_id: int | None = None,
        project_id: int | None = None,
    ) -> TaskPlanResponse:
        user_id = self._normalize_user_id(user_id)
        recent_learnings = TaskLearningService(self.session).list_recent_learnings(user_id=user_id, limit=5)
        prompt = self._build_prompt(input_text, recent_learnings=[learning.summary for learning in recent_learnings])
        try:
            llm = get_chat_model()
            response = llm.invoke(prompt)
        except Exception as exc:
            raise TaskPlanningUnavailableError("planner model unavailable") from exc

        raw_output = self._response_text(response)
        parsed = self._parse_output(raw_output)
        planned = [self._to_planned_task(task) for task in parsed.tasks[:MAX_PLANNED_TASKS]]
        created: list[TaskResponse] = []
        if create_tasks and planned:
            task_service = TaskService(self.session)
            created_rows = task_service.create_many(
                user_id=user_id,
                tasks=[
                    {
                        "title": task.title,
                        "description_md": task.description_md,
                        "priority": task.priority.value if hasattr(task.priority, "value") else str(task.priority),
                        "estimated_pomodoros": task.estimate_minutes,
                        "tags": task.tags,
                        "board_id": board_id,
                        "project_id": project_id,
                        "auto_generated": True,
                        "ai_planned": True,
                        "from_brain_dump": True,
                        "meta": {"planner_rationale": task.rationale} if task.rationale else {},
                    }
                    for task in planned
                ],
            )
            created = [TaskResponse.model_validate(row) for row in created_rows]
        return TaskPlanResponse(tasks=planned, created_tasks=created, rationale=parsed.rationale, raw_output=raw_output)

    @staticmethod
    def _build_prompt(input_text: str, *, recent_learnings: list[str] | None = None) -> str:
        normalized = (input_text or "").strip()
        if not normalized:
            raise TaskValidationError("planner input is required")
        if len(normalized) > MAX_PLANNER_INPUT_CHARS:
            raise TaskValidationError(f"planner input must be {MAX_PLANNER_INPUT_CHARS} characters or fewer")
        learning_context = "\n".join(f"- {item}" for item in recent_learnings or [] if item.strip())
        learning_section = f"\nRecent execution learnings:\n{learning_context}\n" if learning_context else ""
        return f"""You are Alfred's flow-first task planner.
{learning_section}
User dump:
---
{normalized}
---

1. Extract concrete, actionable tasks.
2. Prefer small tasks of 1-4 pomodoros.
3. Assign priority: LOW, MEDIUM, or HIGH.
4. Return ONLY valid JSON in this format:

{{
  "tasks": [
    {{
      "title": "...",
      "description": "...",
      "estimatePomodoros": 1,
      "priority": "MEDIUM",
      "tags": ["deep-work"]
    }}
  ],
  "rationale": "..."
}}"""

    @staticmethod
    def _response_text(response: Any) -> str:
        raw = response.content if hasattr(response, "content") else response
        if isinstance(raw, list):
            return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in raw)
        return str(raw or "")

    @staticmethod
    def _parse_output(raw_output: str) -> _PlannerOutput:
        normalized = (raw_output or "").strip()
        if not normalized:
            raise TaskPlanningParseError("planner returned empty output")
        lowered = normalized.casefold()
        if any(marker in lowered for marker in _REFUSAL_MARKERS):
            raise TaskPlanningParseError("planner returned a refusal instead of JSON")
        fenced = _JSON_FENCE_RE.search(normalized)
        object_match = _JSON_OBJECT_RE.search(normalized)
        candidate = fenced.group(1) if fenced else object_match.group(0) if object_match else normalized
        try:
            payload = json.loads(candidate)
            return _PlannerOutput.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise TaskPlanningParseError("could not parse planner output") from exc

    @staticmethod
    def _to_planned_task(task: _PlannerTask) -> PlannedTask:
        estimate_pomodoros = task.estimatePomodoros or task.estimated_pomodoros
        estimate_minutes = estimate_pomodoros * 25 if estimate_pomodoros else None
        return PlannedTask(
            title=task.title.strip(),
            description_md=task.description_md or task.description or "",
            priority=task.priority,
            estimate_minutes=estimate_minutes,
            tags=task.tags,
        )

    @staticmethod
    def _normalize_user_id(user_id: str) -> str:
        normalized = (user_id or "").strip()
        if not normalized:
            raise TaskValidationError("user_id is required")
        return normalized


__all__ = ["TaskPlanningService"]
