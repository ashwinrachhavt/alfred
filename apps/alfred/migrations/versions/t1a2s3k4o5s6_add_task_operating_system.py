"""add task operating system

Revision ID: t1a2s3k4o5s6
Revises: l9m0n1o2p3q4
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "t1a2s3k4o5s6"
down_revision: str | Sequence[str] | None = "l9m0n1o2p3q4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_type() -> sa.TypeEngine[object]:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "task_boards",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("theme", sa.String(length=64), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("legacy_neuralflow_id", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("legacy_neuralflow_id", name="uq_task_boards_legacy_neuralflow_id"),
    )
    op.create_index("ix_task_boards_user_id", "task_boards", ["user_id"])
    op.create_index("ix_task_boards_user_default", "task_boards", ["user_id", "is_default"], unique=True)

    op.create_table(
        "task_columns",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("board_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("legacy_neuralflow_id", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["board_id"], ["task_boards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("board_id", "position", name="uq_task_columns_board_position"),
        sa.UniqueConstraint("board_id", "name", name="uq_task_columns_board_name"),
        sa.UniqueConstraint("legacy_neuralflow_id", name="uq_task_columns_legacy_neuralflow_id"),
    )
    op.create_index("ix_task_columns_board_id", "task_columns", ["board_id"])

    op.create_table(
        "task_projects",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notion_url", sa.String(length=1000), nullable=True),
        sa.Column("legacy_neuralflow_id", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "slug", name="uq_task_projects_user_slug"),
        sa.UniqueConstraint("legacy_neuralflow_id", name="uq_task_projects_legacy_neuralflow_id"),
    )
    op.create_index("ix_task_projects_user_id", "task_projects", ["user_id"])
    op.create_index("ix_task_projects_status", "task_projects", ["status"])

    op.create_table(
        "tasks",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("board_id", sa.Integer(), nullable=False),
        sa.Column("column_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="TODO"),
        sa.Column("type", sa.String(length=32), nullable=True),
        sa.Column("estimate_minutes", sa.Integer(), nullable=True),
        sa.Column("estimated_pomodoros", sa.Integer(), nullable=True),
        sa.Column("completed_pomodoros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("story_points", sa.Integer(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("tags", _json_type(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("topics", _json_type(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("primary_topic", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("source_kind", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("auto_generated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ai_planned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("from_brain_dump", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ai_state", sa.String(length=32), nullable=False, server_default="RAW"),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("ai_suggested_column_id", sa.Integer(), nullable=True),
        sa.Column("ai_suggested_priority", sa.String(length=16), nullable=True),
        sa.Column("ai_suggested_estimate_min", sa.Integer(), nullable=True),
        sa.Column("ai_subtasks", _json_type(), nullable=True),
        sa.Column("ai_next_action", sa.Text(), nullable=True),
        sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("legacy_neuralflow_id", sa.String(length=255), nullable=True),
        sa.Column("legacy_today_entry_id", sa.Integer(), nullable=True),
        sa.Column("meta", _json_type(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["board_id"], ["task_boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["column_id"], ["task_columns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["task_projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_board_id", "tasks", ["board_id"])
    op.create_index("ix_tasks_column_id", "tasks", ["column_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_due_at", "tasks", ["due_at"])
    op.create_index("ix_tasks_updated_at", "tasks", ["updated_at"])
    op.create_index("ix_tasks_legacy_today_entry_id", "tasks", ["legacy_today_entry_id"], unique=True)
    op.create_index("ix_tasks_legacy_neuralflow_id", "tasks", ["legacy_neuralflow_id"], unique=True)

    op.create_table(
        "task_knowledge_links",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("ref_kind", sa.String(length=64), nullable=False),
        sa.Column("ref_id", sa.String(length=255), nullable=False),
        sa.Column("ref_url", sa.String(length=1000), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("meta", _json_type(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "ref_kind", "ref_id", name="uq_task_knowledge_links_ref"),
    )
    op.create_index("ix_task_knowledge_links_task_id", "task_knowledge_links", ["task_id"])
    op.create_index("ix_task_knowledge_links_ref", "task_knowledge_links", ["ref_kind", "ref_id"])

    op.create_table(
        "task_learnings",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details", _json_type(), nullable=True),
        sa.Column("tags", _json_type(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_learnings_user_id", "task_learnings", ["user_id"])
    op.create_index("ix_task_learnings_task_id", "task_learnings", ["task_id"])

    op.create_table(
        "task_calendar_events",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False, server_default="FOCUS"),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description_md", sa.Text(), nullable=True),
        sa.Column("tags", _json_type(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("location", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_calendar_events_user_start", "task_calendar_events", ["user_id", "start_at"])
    op.create_index("ix_task_calendar_events_task_id", "task_calendar_events", ["task_id"])

    op.create_table(
        "task_focus_sessions",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("interruptions", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["event_id"], ["task_calendar_events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_focus_sessions_user_id", "task_focus_sessions", ["user_id"])
    op.create_index("ix_task_focus_sessions_task_id", "task_focus_sessions", ["task_id"])
    op.create_index("ix_task_focus_sessions_event_id", "task_focus_sessions", ["event_id"])

    op.create_table(
        "task_pomodoro_sessions",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("reflection_md", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_pomodoro_sessions_user_id", "task_pomodoro_sessions", ["user_id"])
    op.create_index("ix_task_pomodoro_sessions_task_id", "task_pomodoro_sessions", ["task_id"])

    op.create_table(
        "task_reward_definitions",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("image_path", sa.String(length=1000), nullable=True),
        sa.Column("rarity", sa.String(length=32), nullable=False, server_default="COMMON"),
        sa.Column("metadata", _json_type(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_task_reward_definitions_slug"),
    )
    op.create_index("ix_task_reward_definitions_slug", "task_reward_definitions", ["slug"], unique=True)

    op.create_table(
        "user_task_rewards",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("reward_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("earned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("metadata", _json_type(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["reward_id"], ["task_reward_definitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_task_rewards_user_id", "user_task_rewards", ["user_id"])
    op.create_index("ix_user_task_rewards_reward_id", "user_task_rewards", ["reward_id"])
    op.create_index("ix_user_task_rewards_task_id", "user_task_rewards", ["task_id"])

    op.create_table(
        "user_task_reward_progress",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("reward_id", sa.Integer(), nullable=False),
        sa.Column("current_shards", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_shards", sa.Integer(), nullable=False, server_default="10"),
        sa.ForeignKeyConstraint(["reward_id"], ["task_reward_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "reward_id", name="uq_user_task_reward_progress_reward"),
    )
    op.create_index("ix_user_task_reward_progress_user_id", "user_task_reward_progress", ["user_id"])

    op.create_table(
        "user_task_gamification_profiles",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("longest_daily_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_daily_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_activity_date", sa.Date(), nullable=True),
        sa.Column("total_tasks_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_deep_work_blocks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_pomodoros", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_task_gamification_profiles_user_id"),
    )
    op.create_index("ix_user_task_gamification_profiles_user_id", "user_task_gamification_profiles", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_user_task_gamification_profiles_user_id", table_name="user_task_gamification_profiles")
    op.drop_table("user_task_gamification_profiles")
    op.drop_index("ix_user_task_reward_progress_user_id", table_name="user_task_reward_progress")
    op.drop_table("user_task_reward_progress")
    op.drop_index("ix_user_task_rewards_task_id", table_name="user_task_rewards")
    op.drop_index("ix_user_task_rewards_reward_id", table_name="user_task_rewards")
    op.drop_index("ix_user_task_rewards_user_id", table_name="user_task_rewards")
    op.drop_table("user_task_rewards")
    op.drop_index("ix_task_reward_definitions_slug", table_name="task_reward_definitions")
    op.drop_table("task_reward_definitions")
    op.drop_index("ix_task_pomodoro_sessions_task_id", table_name="task_pomodoro_sessions")
    op.drop_index("ix_task_pomodoro_sessions_user_id", table_name="task_pomodoro_sessions")
    op.drop_table("task_pomodoro_sessions")
    op.drop_index("ix_task_focus_sessions_event_id", table_name="task_focus_sessions")
    op.drop_index("ix_task_focus_sessions_task_id", table_name="task_focus_sessions")
    op.drop_index("ix_task_focus_sessions_user_id", table_name="task_focus_sessions")
    op.drop_table("task_focus_sessions")
    op.drop_index("ix_task_calendar_events_task_id", table_name="task_calendar_events")
    op.drop_index("ix_task_calendar_events_user_start", table_name="task_calendar_events")
    op.drop_table("task_calendar_events")
    op.drop_index("ix_task_learnings_task_id", table_name="task_learnings")
    op.drop_index("ix_task_learnings_user_id", table_name="task_learnings")
    op.drop_table("task_learnings")
    op.drop_index("ix_task_knowledge_links_ref", table_name="task_knowledge_links")
    op.drop_index("ix_task_knowledge_links_task_id", table_name="task_knowledge_links")
    op.drop_table("task_knowledge_links")
    op.drop_index("ix_tasks_legacy_neuralflow_id", table_name="tasks")
    op.drop_index("ix_tasks_legacy_today_entry_id", table_name="tasks")
    op.drop_index("ix_tasks_updated_at", table_name="tasks")
    op.drop_index("ix_tasks_due_at", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_column_id", table_name="tasks")
    op.drop_index("ix_tasks_board_id", table_name="tasks")
    op.drop_index("ix_tasks_user_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_task_projects_status", table_name="task_projects")
    op.drop_index("ix_task_projects_user_id", table_name="task_projects")
    op.drop_table("task_projects")
    op.drop_index("ix_task_columns_board_id", table_name="task_columns")
    op.drop_table("task_columns")
    op.drop_index("ix_task_boards_user_default", table_name="task_boards")
    op.drop_index("ix_task_boards_user_id", table_name="task_boards")
    op.drop_table("task_boards")
