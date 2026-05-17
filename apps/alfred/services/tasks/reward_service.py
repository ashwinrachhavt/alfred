"""Gamification and rewards service for Alfred tasks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlmodel import Session, select

from alfred.models.tasks import (
    RewardRarity,
    TaskRewardDefinitionRow,
    UserTaskGamificationProfileRow,
    UserTaskRewardProgressRow,
    UserTaskRewardRow,
)
from alfred.services.tasks.exceptions import RewardComputationError, TaskValidationError
from alfred.services.tasks.task_service import TaskService

DEFAULT_REWARDS: tuple[dict[str, Any], ...] = (
    {
        "slug": "first-task-complete",
        "name": "First Task Complete",
        "description": "Completed the first Alfred task.",
        "rarity": RewardRarity.COMMON,
        "metadata_": {"trigger": "task_completed", "threshold": 1},
    },
    {
        "slug": "ten-task-streak",
        "name": "Ten Task Momentum",
        "description": "Completed ten Alfred tasks.",
        "rarity": RewardRarity.RARE,
        "metadata_": {"trigger": "task_completed", "threshold": 10},
    },
    {
        "slug": "deep-work-initiate",
        "name": "Deep Work Initiate",
        "description": "Completed the first focused work block.",
        "rarity": RewardRarity.COMMON,
        "metadata_": {"trigger": "focus_completed", "threshold": 1},
    },
    {
        "slug": "pomodoro-craft",
        "name": "Pomodoro Craft",
        "description": "Logged five pomodoro sessions.",
        "rarity": RewardRarity.RARE,
        "metadata_": {"trigger": "pomodoro_completed", "threshold": 5},
    },
)

XP_BY_EVENT = {
    "task_completed": 25,
    "focus_completed": 40,
    "pomodoro_completed": 15,
}


def _level_for_xp(xp: int) -> int:
    return max(1, int((max(0, xp) / 250) ** 0.5) + 1)


@dataclass(slots=True)
class TaskRewardService:
    session: Session

    def ensure_default_rewards(self) -> list[TaskRewardDefinitionRow]:
        rewards: list[TaskRewardDefinitionRow] = []
        for payload in DEFAULT_REWARDS:
            reward = self.session.exec(
                select(TaskRewardDefinitionRow).where(TaskRewardDefinitionRow.slug == payload["slug"])
            ).first()
            if reward is None:
                reward = TaskRewardDefinitionRow(**payload)
                self.session.add(reward)
                self.session.flush()
            rewards.append(reward)
        self.session.commit()
        for reward in rewards:
            self.session.refresh(reward)
        return rewards

    def get_or_create_profile(self, *, user_id: str) -> UserTaskGamificationProfileRow:
        user_id = self._normalize_user_id(user_id)
        profile = self.session.exec(
            select(UserTaskGamificationProfileRow).where(UserTaskGamificationProfileRow.user_id == user_id)
        ).first()
        if profile is None:
            profile = UserTaskGamificationProfileRow(user_id=user_id)
            self.session.add(profile)
            self.session.commit()
            self.session.refresh(profile)
        return profile

    def record_task_completed(self, *, user_id: str, task_id: int) -> tuple[UserTaskGamificationProfileRow, list[UserTaskRewardRow]]:
        user_id = self._normalize_user_id(user_id)
        TaskService(self.session).get_task(task_id, user_id=user_id)
        profile = self.get_or_create_profile(user_id=user_id)
        profile.total_tasks_completed += 1
        self._record_daily_activity(profile)
        self._grant_xp(profile, XP_BY_EVENT["task_completed"])
        self.session.add(profile)
        self.session.flush()
        rewards = self._award_matching_rewards(
            user_id=user_id,
            event="task_completed",
            counter=profile.total_tasks_completed,
            task_id=task_id,
            source="task_completion",
        )
        self.session.commit()
        self.session.refresh(profile)
        for reward in rewards:
            self.session.refresh(reward)
        return profile, rewards

    def record_focus_completed(self, *, user_id: str, source: str = "focus_session") -> tuple[UserTaskGamificationProfileRow, list[UserTaskRewardRow]]:
        profile = self.get_or_create_profile(user_id=user_id)
        profile.total_deep_work_blocks += 1
        self._record_daily_activity(profile)
        self._grant_xp(profile, XP_BY_EVENT["focus_completed"])
        self.session.add(profile)
        self.session.flush()
        rewards = self._award_matching_rewards(
            user_id=profile.user_id,
            event="focus_completed",
            counter=profile.total_deep_work_blocks,
            source=source,
        )
        self.session.commit()
        self.session.refresh(profile)
        for reward in rewards:
            self.session.refresh(reward)
        return profile, rewards

    def record_pomodoro_completed(self, *, user_id: str, task_id: int | None = None) -> tuple[UserTaskGamificationProfileRow, list[UserTaskRewardRow]]:
        user_id = self._normalize_user_id(user_id)
        if task_id is not None:
            TaskService(self.session).get_task(task_id, user_id=user_id)
        profile = self.get_or_create_profile(user_id=user_id)
        profile.total_pomodoros += 1
        self._record_daily_activity(profile)
        self._grant_xp(profile, XP_BY_EVENT["pomodoro_completed"])
        self.session.add(profile)
        self.session.flush()
        rewards = self._award_matching_rewards(
            user_id=user_id,
            event="pomodoro_completed",
            counter=profile.total_pomodoros,
            task_id=task_id,
            source="pomodoro_completion",
        )
        self.session.commit()
        self.session.refresh(profile)
        for reward in rewards:
            self.session.refresh(reward)
        return profile, rewards

    def list_user_rewards(self, *, user_id: str) -> list[UserTaskRewardRow]:
        user_id = self._normalize_user_id(user_id)
        return list(
            self.session.exec(
                select(UserTaskRewardRow)
                .where(UserTaskRewardRow.user_id == user_id)
                .order_by(UserTaskRewardRow.earned_at.desc(), UserTaskRewardRow.id.desc())
            )
        )

    def _award_matching_rewards(
        self,
        *,
        user_id: str,
        event: str,
        counter: int,
        task_id: int | None = None,
        source: str | None = None,
    ) -> list[UserTaskRewardRow]:
        self.ensure_default_rewards()
        definitions = self.session.exec(select(TaskRewardDefinitionRow)).all()
        awarded: list[UserTaskRewardRow] = []
        for definition in definitions:
            metadata = dict(definition.metadata_ or {})
            if metadata.get("trigger") != event:
                continue
            threshold = int(metadata.get("threshold") or 0)
            if threshold <= 0:
                raise RewardComputationError(f"invalid reward threshold for {definition.slug}")
            progress = self._upsert_progress(user_id=user_id, reward_id=definition.id, current=counter, target=threshold)
            if counter < threshold:
                continue
            already_awarded = self.session.exec(
                select(UserTaskRewardRow)
                .where(UserTaskRewardRow.user_id == user_id)
                .where(UserTaskRewardRow.reward_id == definition.id)
            ).first()
            if already_awarded is not None:
                continue
            reward = UserTaskRewardRow(
                user_id=user_id,
                reward_id=definition.id,
                task_id=task_id,
                source=source,
                note=definition.description,
                metadata_={"event": event, "counter": counter, "target_shards": progress.target_shards},
            )
            self.session.add(reward)
            self.session.flush()
            awarded.append(reward)
        return awarded

    def _upsert_progress(self, *, user_id: str, reward_id: int, current: int, target: int) -> UserTaskRewardProgressRow:
        progress = self.session.exec(
            select(UserTaskRewardProgressRow)
            .where(UserTaskRewardProgressRow.user_id == user_id)
            .where(UserTaskRewardProgressRow.reward_id == reward_id)
        ).first()
        if progress is None:
            progress = UserTaskRewardProgressRow(user_id=user_id, reward_id=reward_id)
        progress.current_shards = min(max(0, current), target)
        progress.target_shards = target
        self.session.add(progress)
        self.session.flush()
        return progress

    @staticmethod
    def _record_daily_activity(profile: UserTaskGamificationProfileRow) -> None:
        today = date.today()
        if profile.last_activity_date == today:
            return
        if profile.last_activity_date == today - timedelta(days=1):
            profile.current_daily_streak += 1
        else:
            profile.current_daily_streak = 1
        profile.longest_daily_streak = max(profile.longest_daily_streak, profile.current_daily_streak)
        profile.last_activity_date = today

    @staticmethod
    def _grant_xp(profile: UserTaskGamificationProfileRow, amount: int) -> None:
        if amount < 0:
            raise RewardComputationError("xp amount must be non-negative")
        profile.xp += amount
        profile.level = _level_for_xp(profile.xp)

    @staticmethod
    def _normalize_user_id(user_id: str) -> str:
        normalized = (user_id or "").strip()
        if not normalized:
            raise TaskValidationError("user_id is required")
        return normalized


__all__ = ["TaskRewardService"]
