from __future__ import annotations

from datetime import datetime, timedelta

from alfred.services.spaced_repetition import compute_next_review_schedule

STAGE_TO_DELTA = {1: timedelta(days=1), 2: timedelta(days=7), 3: timedelta(days=30)}
NOW = datetime(2026, 4, 12, 12, 0, 0)


def test_pass_advances_stage() -> None:
    result = compute_next_review_schedule(
        now=NOW, stage=1, iteration=1, score=0.9,
        pass_threshold=0.8, stage_to_delta=STAGE_TO_DELTA, max_stage=3,
    )
    assert result.stage == 2
    assert result.iteration == 1
    assert result.due_at == NOW + timedelta(days=7)


def test_pass_at_max_stage_increments_iteration() -> None:
    result = compute_next_review_schedule(
        now=NOW, stage=3, iteration=2, score=1.0,
        pass_threshold=0.8, stage_to_delta=STAGE_TO_DELTA, max_stage=3,
    )
    assert result.stage == 3
    assert result.iteration == 3
    assert result.due_at == NOW + timedelta(days=30)


def test_fail_resets_due_to_stage_one() -> None:
    result = compute_next_review_schedule(
        now=NOW, stage=3, iteration=5, score=0.5,
        pass_threshold=0.8, stage_to_delta=STAGE_TO_DELTA, max_stage=3,
    )
    assert result.stage == 3  # stage preserved
    assert result.iteration == 5  # iteration preserved
    assert result.due_at == NOW + timedelta(days=1)  # resets to 1-day interval


def test_none_score_treated_as_fail() -> None:
    result = compute_next_review_schedule(
        now=NOW, stage=2, iteration=1, score=None,
        pass_threshold=0.8, stage_to_delta=STAGE_TO_DELTA, max_stage=3,
    )
    assert result.stage == 2
    assert result.due_at == NOW + timedelta(days=1)
