"""add streaming tables

Creates three tables:
  - agent_runs            one row per AI invocation; nested via parent_run_id
  - agent_run_events      append-only event log (source of truth)
  - agent_run_snapshots   periodic + terminal compaction for cheap replay

Spec: docs/superpowers/specs/2026-05-01-streaming-revamp-design.md section 5
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "s0t1r2e3a4m5"
down_revision: str | Sequence[str] | None = "i3j4k5l6m7n8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("parent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("thread_id", sa.Integer(), nullable=True),
        sa.Column("run_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("model_id", sa.String(length=128), nullable=True),
        sa.Column("active_lens", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("error_type", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()),
                  server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["thinking_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_agent_runs_thread", "agent_runs", ["thread_id", "started_at"])
    op.create_index("idx_agent_runs_parent", "agent_runs", ["parent_run_id"])
    op.create_index("idx_agent_runs_user_time", "agent_runs", ["user_id", "started_at"])
    op.create_index(
        "idx_agent_runs_status_running",
        "agent_runs", ["status"],
        postgresql_where=sa.text("status = 'running'"),
    )

    op.create_table(
        "agent_run_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("emitted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("clock_timestamp()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "seq", name="uq_run_events_run_seq"),
    )
    op.create_index("idx_run_events_run_seq", "agent_run_events", ["run_id", "seq"])
    op.create_index("idx_run_events_type_time", "agent_run_events", ["event_type", "emitted_at"])
    op.create_index(
        "idx_run_events_payload_gin",
        "agent_run_events", ["payload"],
        postgresql_using="gin",
        postgresql_ops={"payload": "jsonb_path_ops"},
    )

    op.create_table(
        "agent_run_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("up_to_seq", sa.Integer(), nullable=False),
        sa.Column("state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("message_text", sa.Text(),
                  server_default=sa.text("''"), nullable=False),
        sa.Column("thinking_text", sa.Text(),
                  server_default=sa.text("''"), nullable=False),
        sa.Column("tokens_so_far", sa.Integer(),
                  server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "up_to_seq", name="uq_run_snapshots_run_seq"),
    )
    op.create_index("idx_run_snapshots_run", "agent_run_snapshots", ["run_id", "up_to_seq"])


def downgrade() -> None:
    op.drop_index("idx_run_snapshots_run", table_name="agent_run_snapshots")
    op.drop_table("agent_run_snapshots")

    op.drop_index("idx_run_events_payload_gin", table_name="agent_run_events")
    op.drop_index("idx_run_events_type_time", table_name="agent_run_events")
    op.drop_index("idx_run_events_run_seq", table_name="agent_run_events")
    op.drop_table("agent_run_events")

    op.drop_index("idx_agent_runs_status_running", table_name="agent_runs")
    op.drop_index("idx_agent_runs_user_time", table_name="agent_runs")
    op.drop_index("idx_agent_runs_parent", table_name="agent_runs")
    op.drop_index("idx_agent_runs_thread", table_name="agent_runs")
    op.drop_table("agent_runs")
