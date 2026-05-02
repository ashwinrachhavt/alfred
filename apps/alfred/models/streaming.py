"""SQLModel tables backing the streaming substrate.

Three tables:
  - agent_runs            one row per invocation; nested via parent_run_id
  - agent_run_events      append-only typed event log (source of truth)
  - agent_run_snapshots   periodic + terminal compaction for cheap replay

Spec: docs/superpowers/specs/2026-05-01-streaming-revamp-design.md section 5
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel


class AgentRunRow(SQLModel, table=True):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("idx_agent_runs_thread", "thread_id", "started_at"),
        Index("idx_agent_runs_parent", "parent_run_id"),
        Index("idx_agent_runs_user_time", "user_id", "started_at"),
        Index("idx_agent_runs_status_running", "status",
              postgresql_where=(Column("status") == "running")),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    parent_run_id: UUID | None = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=True),
                         ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=True),
    )
    thread_id: int | None = Field(
        default=None,
        sa_column=Column(Integer,
                         ForeignKey("thinking_sessions.id", ondelete="CASCADE"), nullable=True),
    )
    run_type: str = Field(sa_column=Column(String(32), nullable=False))
    status: str = Field(sa_column=Column(String(16), nullable=False))
    user_id: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    input_summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    model_id: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    active_lens: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))

    started_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    finished_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    duration_ms: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    tokens_in: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    tokens_out: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    cost_usd: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 6), nullable=True))

    error_type: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    metadata_: dict = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSONB, nullable=False, server_default="{}"),
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )


class AgentRunEventRow(SQLModel, table=True):
    __tablename__ = "agent_run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_run_events_run_seq"),
        Index("idx_run_events_run_seq", "run_id", "seq"),
        Index("idx_run_events_type_time", "event_type", "emitted_at"),
        Index("idx_run_events_payload_gin", "payload",
              postgresql_using="gin", postgresql_ops={"payload": "jsonb_path_ops"}),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    run_id: UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True),
                         ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
    )
    seq: int = Field(sa_column=Column(Integer, nullable=False))
    event_type: str = Field(sa_column=Column(String(48), nullable=False))
    payload: dict = Field(
        sa_column=Column(JSONB, nullable=False),
    )
    emitted_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False,
                         server_default=func.clock_timestamp()),
    )


class AgentRunSnapshotRow(SQLModel, table=True):
    __tablename__ = "agent_run_snapshots"
    __table_args__ = (
        UniqueConstraint("run_id", "up_to_seq", name="uq_run_snapshots_run_seq"),
        Index("idx_run_snapshots_run", "run_id", "up_to_seq"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    run_id: UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True),
                         ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
    )
    up_to_seq: int = Field(sa_column=Column(Integer, nullable=False))
    state: dict = Field(sa_column=Column(JSONB, nullable=False))
    message_text: str = Field(
        default="", sa_column=Column(Text, nullable=False, server_default=""),
    )
    thinking_text: str = Field(
        default="", sa_column=Column(Text, nullable=False, server_default=""),
    )
    tokens_so_far: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )


__all__ = ["AgentRunRow", "AgentRunEventRow", "AgentRunSnapshotRow"]
