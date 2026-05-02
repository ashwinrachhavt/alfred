"""SQLModel tables backing the streaming substrate.

Three tables:
  - agent_runs            one row per invocation; nested via parent_run_id
  - agent_run_events      append-only typed event log (source of truth)
  - agent_run_snapshots   periodic + terminal compaction for cheap replay

Spec: docs/superpowers/specs/2026-05-01-streaming-revamp-design.md section 5

Dialect portability: Postgres gets JSONB/UUID/BIGSERIAL natively; other dialects
(SQLite in tests) get JSON/String(36)/Integer fallbacks via `.with_variant()`.
Follows the existing Alfred idiom in notes.py, company.py, datastore.py.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import (
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
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel


class _PortableUUID(TypeDecorator):
    """Portable UUID type: native UUID on Postgres, CHAR(36) with string conversion elsewhere."""

    impl = sa.String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(sa.String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        # For other dialects (SQLite), convert UUID to string
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        # For other dialects (SQLite), convert string back to UUID
        if isinstance(value, str):
            return UUID(value)
        return value


def _uuid_column() -> sa.types.TypeEngine:
    """Portable UUID column type: native UUID on Postgres, CHAR(36) elsewhere."""
    return _PortableUUID()


def _jsonb_column() -> sa.types.TypeEngine:
    """Portable JSONB column type: native JSONB on Postgres, JSON elsewhere."""
    return sa.JSON().with_variant(JSONB(), "postgresql")


def _bigint_pk_column() -> sa.types.TypeEngine:
    """Portable BIGSERIAL-like PK: BigInteger on Postgres, Integer on SQLite."""
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


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
        sa_column=Column(_uuid_column(), primary_key=True),
    )
    parent_run_id: UUID | None = Field(
        default=None,
        sa_column=Column(_uuid_column(),
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
        sa_column=Column("metadata", _jsonb_column(), nullable=False, server_default="{}"),
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
        default=None, sa_column=Column(_bigint_pk_column(), primary_key=True, autoincrement=True),
    )
    run_id: UUID = Field(
        sa_column=Column(_uuid_column(),
                         ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
    )
    seq: int = Field(sa_column=Column(Integer, nullable=False))
    event_type: str = Field(sa_column=Column(String(48), nullable=False))
    payload: dict = Field(
        sa_column=Column(_jsonb_column(), nullable=False),
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
        default=None, sa_column=Column(_bigint_pk_column(), primary_key=True, autoincrement=True),
    )
    run_id: UUID = Field(
        sa_column=Column(_uuid_column(),
                         ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
    )
    up_to_seq: int = Field(sa_column=Column(Integer, nullable=False))
    state: dict = Field(sa_column=Column(_jsonb_column(), nullable=False))
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
