"""Pydantic schemas for the Alfred task operating system API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from alfred.models.tasks import (
    ProjectStatus,
    RewardRarity,
    TaskAiState,
    TaskEventType,
    TaskPriority,
    TaskStatus,
    TaskType,
)


class TaskApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TaskBoardResponse(TaskApiModel):
    id: int
    user_id: str
    title: str
    description: str | None = None
    theme: str | None = None
    is_default: bool
    legacy_neuralflow_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskColumnResponse(TaskApiModel):
    id: int
    board_id: int
    name: str
    position: int
    legacy_neuralflow_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    slug: str | None = Field(default=None, max_length=255)
    status: ProjectStatus = ProjectStatus.ACTIVE
    notion_url: str | None = Field(default=None, max_length=1000)


class TaskProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: ProjectStatus | None = None
    notion_url: str | None = Field(default=None, max_length=1000)


class TaskProjectResponse(TaskApiModel):
    id: int
    user_id: str
    slug: str
    title: str
    description: str | None = None
    status: str
    points: int = 0
    notion_url: str | None = None
    legacy_neuralflow_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description_md: str = ""
    board_id: int | None = None
    column_id: int | None = None
    project_id: int | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    type: TaskType | None = None
    estimate_minutes: int | None = Field(default=None, ge=1)
    estimated_pomodoros: int | None = Field(default=None, ge=1)
    story_points: int | None = Field(default=None, ge=0)
    due_at: datetime | None = None
    due_date: date | None = None
    tags: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    primary_topic: str | None = Field(default=None, max_length=255)
    source: str | None = Field(default=None, max_length=255)
    source_kind: str | None = Field(default=None, max_length=64)
    source_id: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=1000)
    auto_generated: bool = False
    ai_planned: bool = False
    from_brain_dump: bool = False
    ai_state: TaskAiState = TaskAiState.RAW
    ai_confidence: float | None = Field(default=None, ge=0, le=1)
    ai_suggested_column_id: int | None = None
    ai_suggested_priority: TaskPriority | None = None
    ai_suggested_estimate_min: int | None = Field(default=None, ge=1)
    ai_subtasks: list[dict[str, Any]] | None = None
    ai_next_action: str | None = None
    legacy_neuralflow_id: str | None = Field(default=None, max_length=255)
    legacy_today_entry_id: int | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description_md: str | None = None
    board_id: int | None = None
    column_id: int | None = None
    project_id: int | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    type: TaskType | None = None
    estimate_minutes: int | None = Field(default=None, ge=1)
    estimated_pomodoros: int | None = Field(default=None, ge=1)
    completed_pomodoros: int | None = Field(default=None, ge=0)
    story_points: int | None = Field(default=None, ge=0)
    due_at: datetime | None = None
    due_date: date | None = None
    tags: list[str] | None = None
    topics: list[str] | None = None
    primary_topic: str | None = Field(default=None, max_length=255)
    source: str | None = Field(default=None, max_length=255)
    source_kind: str | None = Field(default=None, max_length=64)
    source_id: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=1000)
    auto_generated: bool | None = None
    ai_planned: bool | None = None
    from_brain_dump: bool | None = None
    ai_state: TaskAiState | None = None
    ai_confidence: float | None = Field(default=None, ge=0, le=1)
    ai_suggested_column_id: int | None = None
    ai_suggested_priority: TaskPriority | None = None
    ai_suggested_estimate_min: int | None = Field(default=None, ge=1)
    ai_subtasks: list[dict[str, Any]] | None = None
    ai_next_action: str | None = None
    meta: dict[str, Any] | None = None


class TaskMoveRequest(BaseModel):
    board_id: int | None = None
    column_id: int
    position: int | None = Field(default=None, ge=0)


class TaskDoneRequest(BaseModel):
    reflection_md: str | None = None
    completed_at: datetime | None = None
    award_rewards: bool = True


class TaskResponse(TaskApiModel):
    id: int
    user_id: str
    board_id: int
    column_id: int
    project_id: int | None = None
    title: str
    description_md: str = ""
    priority: str
    status: str
    type: str | None = None
    estimate_minutes: int | None = None
    estimated_pomodoros: int | None = None
    completed_pomodoros: int = 0
    story_points: int | None = None
    due_at: datetime | None = None
    due_date: date | None = None
    tags: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    primary_topic: str | None = None
    source: str | None = None
    source_kind: str | None = None
    source_id: str | None = None
    source_url: str | None = None
    auto_generated: bool = False
    ai_planned: bool = False
    from_brain_dump: bool = False
    ai_state: str
    ai_confidence: float | None = None
    ai_suggested_column_id: int | None = None
    ai_suggested_priority: str | None = None
    ai_suggested_estimate_min: int | None = None
    ai_subtasks: list[dict[str, Any]] | None = None
    ai_next_action: str | None = None
    enriched_at: datetime | None = None
    completed_at: datetime | None = None
    legacy_neuralflow_id: str | None = None
    legacy_today_entry_id: int | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int
    next_cursor: str | None = None


class TaskKnowledgeLinkCreate(BaseModel):
    ref_kind: str = Field(min_length=1, max_length=64)
    ref_id: str = Field(min_length=1, max_length=255)
    ref_url: str | None = Field(default=None, max_length=1000)
    title: str | None = Field(default=None, max_length=500)
    meta: dict[str, Any] = Field(default_factory=dict)


class TaskKnowledgeLinkResponse(TaskKnowledgeLinkCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskLearningCreate(BaseModel):
    task_id: int
    summary: str = Field(min_length=1)
    details: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


class TaskLearningResponse(TaskLearningCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskCalendarEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    start_at: datetime
    end_at: datetime
    task_id: int | None = None
    tz_name: str = "UTC"
    type: TaskEventType = TaskEventType.FOCUS
    description_md: str | None = None
    location: str | None = Field(default=None, max_length=500)
    tags: list[str] = Field(default_factory=list)


class TaskCalendarEventResponse(TaskApiModel):
    id: int
    user_id: str
    task_id: int | None = None
    title: str
    type: str
    start_at: datetime
    end_at: datetime
    description_md: str | None = None
    tags: list[str] = Field(default_factory=list)
    location: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskFocusSessionCreate(BaseModel):
    task_id: int | None = None
    event_id: int | None = None
    started_at: datetime | None = None


class TaskFocusSessionComplete(BaseModel):
    ended_at: datetime | None = None
    interruptions: int | None = Field(default=None, ge=0)


class TaskFocusSessionResponse(TaskApiModel):
    id: int
    user_id: str
    task_id: int | None = None
    event_id: int | None = None
    started_at: datetime
    ended_at: datetime | None = None
    completed: bool
    interruptions: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskPomodoroCreate(BaseModel):
    task_id: int
    start_time: datetime
    end_time: datetime
    duration_minutes: int = Field(gt=0)
    reflection_md: str | None = None
    status: str = Field(default="completed", max_length=32)


class TaskPomodoroResponse(TaskApiModel):
    id: int
    user_id: str
    task_id: int
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    reflection_md: str | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskRewardDefinitionResponse(TaskApiModel):
    id: int
    slug: str
    name: str
    description: str
    image_path: str | None = None
    rarity: str = RewardRarity.COMMON
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata")
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserTaskRewardResponse(TaskApiModel):
    id: int
    user_id: str
    reward_id: int
    task_id: int | None = None
    earned_at: datetime
    source: str | None = None
    note: str | None = None
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata")
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserTaskRewardProgressResponse(TaskApiModel):
    id: int
    user_id: str
    reward_id: int
    current_shards: int
    target_shards: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserTaskGamificationProfileResponse(TaskApiModel):
    id: int
    user_id: str
    xp: int
    level: int
    longest_daily_streak: int
    current_daily_streak: int
    last_activity_date: date | None = None
    total_tasks_completed: int
    total_deep_work_blocks: int
    total_pomodoros: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskDoneResponse(BaseModel):
    task: TaskResponse
    profile: UserTaskGamificationProfileResponse | None = None
    rewards: list[UserTaskRewardResponse] = Field(default_factory=list)


class PlannedTask(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description_md: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    type: TaskType | None = None
    estimate_minutes: int | None = Field(default=None, ge=1)
    tags: list[str] = Field(default_factory=list)
    rationale: str | None = None


class TaskPlanRequest(BaseModel):
    input: str = Field(min_length=1)
    create_tasks: bool = False
    board_id: int | None = None
    project_id: int | None = None


class TaskPlanResponse(BaseModel):
    tasks: list[PlannedTask] = Field(default_factory=list)
    created_tasks: list[TaskResponse] = Field(default_factory=list)
    rationale: str | None = None
    raw_output: str | None = None


__all__ = [name for name in globals() if name.startswith("Task") or name.startswith("UserTask") or name == "PlannedTask"]
