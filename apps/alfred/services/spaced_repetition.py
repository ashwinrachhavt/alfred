from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Mapping


@dataclass(frozen=True, slots=True)
class NextReviewSchedule:
    """Next review schedule computed from a completed review."""

    stage: int
    iteration: int
    due_at: datetime


def compute_next_review_schedule(
    *,
    now: datetime,
    stage: int,
    iteration: int,
    score: float | None,
    pass_threshold: float,
    stage_to_delta: Mapping[int, timedelta],
    max_stage: int,
    reset_stage: int = 1,
) -> NextReviewSchedule:
    """Compute the next review schedule for a spaced-repetition system.

    Behavior:
    - Passing score advances stage up to `max_stage`.
    - Once at `max_stage`, passing increments `iteration` and keeps stage fixed.
    - Failing score resets due date to `reset_stage` while keeping stage/iteration unchanged.
    """

    effective_score = float(score) if score is not None else 0.0

    if effective_score >= pass_threshold:
        next_stage = min(int(max_stage), int(stage) + 1)
        next_iteration = int(iteration)
        if int(stage) >= int(max_stage):
            next_stage = int(max_stage)
            next_iteration = int(iteration) + 1
        due_at = now + stage_to_delta[next_stage]
        return NextReviewSchedule(stage=next_stage, iteration=next_iteration, due_at=due_at)

    due_at = now + stage_to_delta[int(reset_stage)]
    return NextReviewSchedule(stage=int(stage), iteration=int(iteration), due_at=due_at)
