"""Alfred-native task operating system models.

These tables port Neuralflow's todo domain into Alfred's SQLModel/FastAPI
architecture. ``DailyEntryRow`` remains a compatibility and migration source;
these rows are the durable task source of truth.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from alfred.models.base import Model


class TaskStatus(StrEnum):
    BACKLOG = "BACKLOG"
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    ARCHIVED = "ARCHIVED"


class TaskPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TaskType(StrEnum):
    DEEP_WORK = "DEEP_WORK"
    SHALLOW_WORK = "SHALLOW_WORK"
    LEARNING = "LEARNING"
    SHIP = "SHIP"
    MAINTENANCE = "MAINTENANCE"


class TaskAiState(StrEnum):
    RAW = "RAW"
    CLASSIFIED = "CLASSIFIED"
    ENRICHED = "ENRICHED"
    SUGGESTED = "SUGGESTED"
    COMPLETED = "COMPLETED"


class ProjectStatus(StrEnum):
    ACTIVE = "ACTIVE"
    HOLD = "HOLD"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class TaskEventType(StrEnum):
    FOCUS = "FOCUS"
    MEETING = "MEETING"
    PERSONAL = "PERSONAL"
    BREAK = "BREAK"


class RewardRarity(StrEnum):
    COMMON = "COMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"


class TaskBoardRow(Model, table=True):
    """A per-user task board, usually the default personal kanban."""

    __tablename__ = "task_boards"
    __table_args__ = (
        sa.Index("ix_task_boards_user_id", "user_id"),
        sa.Index("ix_task_boards_user_default", "user_id", "is_default", unique=True),
    )

    user_id: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False))
    title: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False))
    description: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    theme: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=64), nullable=True))
    is_default: bool = Field(default=False, sa_column=sa.Column(sa.Boolean, nullable=False))
    legacy_neuralflow_id: str | None = Field(
        default=None,
        sa_column=sa.Column(sa.String(length=255), nullable=True, unique=True),
    )


class TaskColumnRow(Model, table=True):
    """Ordered column inside a task board."""

    __tablename__ = "task_columns"
    __table_args__ = (
        sa.Index("ix_task_columns_board_id", "board_id"),
        sa.UniqueConstraint("board_id", "position", name="uq_task_columns_board_position"),
        sa.UniqueConstraint("board_id", "name", name="uq_task_columns_board_name"),
    )

    board_id: int = Field(
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("task_boards.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    name: str = Field(sa_column=sa.Column(sa.String(length=120), nullable=False))
    position: int = Field(sa_column=sa.Column(sa.Integer, nullable=False))
    legacy_neuralflow_id: str | None = Field(
        default=None,
        sa_column=sa.Column(sa.String(length=255), nullable=True, unique=True),
    )


class TaskProjectRow(Model, table=True):
    """Lightweight project grouping for tasks and linked knowledge artifacts."""

    __tablename__ = "task_projects"
    __table_args__ = (
        sa.Index("ix_task_projects_user_id", "user_id"),
        sa.Index("ix_task_projects_status", "status"),
        sa.UniqueConstraint("user_id", "slug", name="uq_task_projects_user_slug"),
    )

    user_id: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False))
    slug: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False))
    title: str = Field(sa_column=sa.Column(sa.String(length=500), nullable=False))
    description: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    status: str = Field(default=ProjectStatus.ACTIVE, sa_column=sa.Column(sa.String(32), nullable=False))
    points: int = Field(default=0, sa_column=sa.Column(sa.Integer, nullable=False))
    notion_url: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=1000)))
    legacy_neuralflow_id: str | None = Field(
        default=None,
        sa_column=sa.Column(sa.String(length=255), nullable=True, unique=True),
    )


class TaskRow(Model, table=True):
    """Durable Alfred task, ported from Neuralflow's Prisma Task model."""

    __tablename__ = "tasks"
    __table_args__ = (
        sa.Index("ix_tasks_user_id", "user_id"),
        sa.Index("ix_tasks_board_id", "board_id"),
        sa.Index("ix_tasks_column_id", "column_id"),
        sa.Index("ix_tasks_status", "status"),
        sa.Index("ix_tasks_due_at", "due_at"),
        sa.Index("ix_tasks_updated_at", "updated_at"),
        sa.Index("ix_tasks_legacy_today_entry_id", "legacy_today_entry_id", unique=True),
        sa.Index("ix_tasks_legacy_neuralflow_id", "legacy_neuralflow_id", unique=True),
    )

    user_id: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False))
    board_id: int = Field(
        sa_column=sa.Column(sa.Integer, sa.ForeignKey("task_boards.id", ondelete="CASCADE"), nullable=False),
    )
    column_id: int = Field(
        sa_column=sa.Column(sa.Integer, sa.ForeignKey("task_columns.id", ondelete="CASCADE"), nullable=False),
    )
    project_id: int | None = Field(
        default=None,
        sa_column=sa.Column(sa.Integer, sa.ForeignKey("task_projects.id", ondelete="SET NULL")),
    )
    title: str = Field(sa_column=sa.Column(sa.String(length=500), nullable=False))
    description_md: str = Field(default="", sa_column=sa.Column(sa.Text, nullable=False))
    priority: str = Field(default=TaskPriority.MEDIUM, sa_column=sa.Column(sa.String(16), nullable=False))
    status: str = Field(default=TaskStatus.TODO, sa_column=sa.Column(sa.String(32), nullable=False))
    type: str | None = Field(default=None, sa_column=sa.Column(sa.String(32), nullable=True))
    estimate_minutes: int | None = Field(default=None, sa_column=sa.Column(sa.Integer, nullable=True))
    estimated_pomodoros: int | None = Field(default=None, sa_column=sa.Column(sa.Integer, nullable=True))
    completed_pomodoros: int = Field(default=0, sa_column=sa.Column(sa.Integer, nullable=False))
    story_points: int | None = Field(default=None, sa_column=sa.Column(sa.Integer, nullable=True))
    due_at: datetime | None = Field(default=None, sa_column=sa.Column(sa.DateTime(timezone=True)))
    due_date: date | None = Field(default=None, sa_column=sa.Column(sa.Date, nullable=True))
    tags: list[str] = Field(default_factory=list, sa_column=sa.Column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False))
    topics: list[str] = Field(default_factory=list, sa_column=sa.Column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False))
    primary_topic: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=255)))
    source: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=255)))
    source_kind: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=64)))
    source_id: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=255)))
    source_url: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=1000)))
    auto_generated: bool = Field(default=False, sa_column=sa.Column(sa.Boolean, nullable=False))
    ai_planned: bool = Field(default=False, sa_column=sa.Column(sa.Boolean, nullable=False))
    from_brain_dump: bool = Field(default=False, sa_column=sa.Column(sa.Boolean, nullable=False))
    ai_state: str = Field(default=TaskAiState.RAW, sa_column=sa.Column(sa.String(32), nullable=False))
    ai_confidence: float | None = Field(default=None, sa_column=sa.Column(sa.Float, nullable=True))
    ai_suggested_column_id: int | None = Field(default=None, sa_column=sa.Column(sa.Integer, nullable=True))
    ai_suggested_priority: str | None = Field(default=None, sa_column=sa.Column(sa.String(16), nullable=True))
    ai_suggested_estimate_min: int | None = Field(default=None, sa_column=sa.Column(sa.Integer, nullable=True))
    ai_subtasks: list[dict[str, Any]] | None = Field(default=None, sa_column=sa.Column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=True))
    ai_next_action: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    enriched_at: datetime | None = Field(default=None, sa_column=sa.Column(sa.DateTime(timezone=True)))
    completed_at: datetime | None = Field(default=None, sa_column=sa.Column(sa.DateTime(timezone=True)))
    legacy_neuralflow_id: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=255), nullable=True))
    legacy_today_entry_id: int | None = Field(default=None, sa_column=sa.Column(sa.Integer, nullable=True))
    meta: dict[str, Any] = Field(default_factory=dict, sa_column=sa.Column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False))


class TaskKnowledgeLinkRow(Model, table=True):
    """Trace a task back to notes, zettels, captures, documents, or external sources."""

    __tablename__ = "task_knowledge_links"
    __table_args__ = (
        sa.Index("ix_task_knowledge_links_task_id", "task_id"),
        sa.Index("ix_task_knowledge_links_ref", "ref_kind", "ref_id"),
        sa.UniqueConstraint("task_id", "ref_kind", "ref_id", name="uq_task_knowledge_links_ref"),
    )

    task_id: int = Field(sa_column=sa.Column(sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False))
    ref_kind: str = Field(sa_column=sa.Column(sa.String(length=64), nullable=False))
    ref_id: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False))
    ref_url: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=1000), nullable=True))
    title: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=500), nullable=True))
    meta: dict[str, Any] = Field(default_factory=dict, sa_column=sa.Column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False))


class TaskLearningRow(Model, table=True):
    """Learning captured from task completion, reflection, or planner feedback."""

    __tablename__ = "task_learnings"
    __table_args__ = (
        sa.Index("ix_task_learnings_user_id", "user_id"),
        sa.Index("ix_task_learnings_task_id", "task_id"),
    )

    user_id: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False))
    task_id: int = Field(sa_column=sa.Column(sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False))
    summary: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    details: dict[str, Any] | None = Field(default=None, sa_column=sa.Column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=True))
    tags: list[str] = Field(default_factory=list, sa_column=sa.Column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False))
    confidence: float | None = Field(default=None, sa_column=sa.Column(sa.Float, nullable=True))


class TaskCalendarEventRow(Model, table=True):
    """Calendar/focus event related to a task."""

    __tablename__ = "task_calendar_events"
    __table_args__ = (
        sa.Index("ix_task_calendar_events_user_start", "user_id", "start_at"),
        sa.Index("ix_task_calendar_events_task_id", "task_id"),
    )

    user_id: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False))
    task_id: int | None = Field(default=None, sa_column=sa.Column(sa.Integer, sa.ForeignKey("tasks.id", ondelete="SET NULL")))
    title: str = Field(sa_column=sa.Column(sa.String(length=500), nullable=False))
    type: str = Field(default=TaskEventType.FOCUS, sa_column=sa.Column(sa.String(32), nullable=False))
    start_at: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))
    end_at: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))
    description_md: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    tags: list[str] = Field(default_factory=list, sa_column=sa.Column(sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False))
    location: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=500), nullable=True))


class TaskFocusSessionRow(Model, table=True):
    """Execution record for a scheduled or ad-hoc focus block."""

    __tablename__ = "task_focus_sessions"
    __table_args__ = (
        sa.Index("ix_task_focus_sessions_user_id", "user_id"),
        sa.Index("ix_task_focus_sessions_task_id", "task_id"),
        sa.Index("ix_task_focus_sessions_event_id", "event_id"),
    )

    user_id: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False))
    task_id: int | None = Field(default=None, sa_column=sa.Column(sa.Integer, sa.ForeignKey("tasks.id", ondelete="SET NULL")))
    event_id: int | None = Field(default=None, sa_column=sa.Column(sa.Integer, sa.ForeignKey("task_calendar_events.id", ondelete="SET NULL")))
    started_at: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))
    ended_at: datetime | None = Field(default=None, sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True))
    completed: bool = Field(default=False, sa_column=sa.Column(sa.Boolean, nullable=False))
    interruptions: int = Field(default=0, sa_column=sa.Column(sa.Integer, nullable=False))


class TaskPomodoroSessionRow(Model, table=True):
    """Pomodoro completion/reflection record for a task."""

    __tablename__ = "task_pomodoro_sessions"
    __table_args__ = (
        sa.Index("ix_task_pomodoro_sessions_user_id", "user_id"),
        sa.Index("ix_task_pomodoro_sessions_task_id", "task_id"),
    )

    user_id: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False))
    task_id: int = Field(sa_column=sa.Column(sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False))
    start_time: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))
    end_time: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))
    duration_minutes: int = Field(sa_column=sa.Column(sa.Integer, nullable=False))
    reflection_md: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    status: str = Field(sa_column=sa.Column(sa.String(length=32), nullable=False))


class TaskRewardDefinitionRow(Model, table=True):
    """Reward catalog item ported from Neuralflow stones/achievements."""

    __tablename__ = "task_reward_definitions"
    __table_args__ = (sa.Index("ix_task_reward_definitions_slug", "slug", unique=True),)

    slug: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False, unique=True))
    name: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False))
    description: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    image_path: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=1000), nullable=True))
    rarity: str = Field(default=RewardRarity.COMMON, sa_column=sa.Column(sa.String(32), nullable=False))
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=sa.Column("metadata", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
    )


class UserTaskRewardRow(Model, table=True):
    """Reward earned by a user for task/focus activity."""

    __tablename__ = "user_task_rewards"
    __table_args__ = (
        sa.Index("ix_user_task_rewards_user_id", "user_id"),
        sa.Index("ix_user_task_rewards_reward_id", "reward_id"),
        sa.Index("ix_user_task_rewards_task_id", "task_id"),
    )

    user_id: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False))
    reward_id: int = Field(sa_column=sa.Column(sa.Integer, sa.ForeignKey("task_reward_definitions.id", ondelete="CASCADE"), nullable=False))
    task_id: int | None = Field(default=None, sa_column=sa.Column(sa.Integer, sa.ForeignKey("tasks.id", ondelete="SET NULL")))
    earned_at: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    source: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=255), nullable=True))
    note: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=sa.Column("metadata", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
    )


class UserTaskRewardProgressRow(Model, table=True):
    """Shard/progress tracker for future Alfred reward moments."""

    __tablename__ = "user_task_reward_progress"
    __table_args__ = (
        sa.Index("ix_user_task_reward_progress_user_id", "user_id"),
        sa.UniqueConstraint("user_id", "reward_id", name="uq_user_task_reward_progress_reward"),
    )

    user_id: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False))
    reward_id: int = Field(sa_column=sa.Column(sa.Integer, sa.ForeignKey("task_reward_definitions.id", ondelete="CASCADE"), nullable=False))
    current_shards: int = Field(default=0, sa_column=sa.Column(sa.Integer, nullable=False))
    target_shards: int = Field(default=10, sa_column=sa.Column(sa.Integer, nullable=False))


class UserTaskGamificationProfileRow(Model, table=True):
    """Per-user task gamification counters."""

    __tablename__ = "user_task_gamification_profiles"
    __table_args__ = (sa.Index("ix_user_task_gamification_profiles_user_id", "user_id", unique=True),)

    user_id: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False, unique=True))
    xp: int = Field(default=0, sa_column=sa.Column(sa.Integer, nullable=False))
    level: int = Field(default=1, sa_column=sa.Column(sa.Integer, nullable=False))
    longest_daily_streak: int = Field(default=0, sa_column=sa.Column(sa.Integer, nullable=False))
    current_daily_streak: int = Field(default=0, sa_column=sa.Column(sa.Integer, nullable=False))
    last_activity_date: date | None = Field(default=None, sa_column=sa.Column(sa.Date, nullable=True))
    total_tasks_completed: int = Field(default=0, sa_column=sa.Column(sa.Integer, nullable=False))
    total_deep_work_blocks: int = Field(default=0, sa_column=sa.Column(sa.Integer, nullable=False))
    total_pomodoros: int = Field(default=0, sa_column=sa.Column(sa.Integer, nullable=False))


__all__ = [
    "ProjectStatus",
    "RewardRarity",
    "TaskAiState",
    "TaskBoardRow",
    "TaskCalendarEventRow",
    "TaskColumnRow",
    "TaskEventType",
    "TaskFocusSessionRow",
    "TaskKnowledgeLinkRow",
    "TaskLearningRow",
    "TaskPomodoroSessionRow",
    "TaskPriority",
    "TaskProjectRow",
    "TaskRewardDefinitionRow",
    "TaskRow",
    "TaskStatus",
    "TaskType",
    "UserTaskGamificationProfileRow",
    "UserTaskRewardProgressRow",
    "UserTaskRewardRow",
]
