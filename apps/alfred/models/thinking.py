"""Thinking canvas session models + Agent chat thread models (Postgres, SQLModel).

ThinkingSessionRow serves as the shared session/thread table for both:
- Canvas sessions (type='canvas'): structured blocks for thinking canvases
- Agent threads (type='agent'): chat conversations with the AI agent

AgentMessageRow stores individual messages for agent chat threads.
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, String, Text
from sqlmodel import Field

from alfred.models.base import Model


class ThinkingSessionRow(Model, table=True):
    """A thinking/agent session.

    ┌──────────────────────────────────────────────┐
    │  ThinkingSessionRow                          │
    │  type='canvas' → blocks[] used               │
    │  type='agent'  → AgentMessageRow children    │
    └──────────────────────────────────────────────┘
    """

    __tablename__ = "thinking_sessions"
    __table_args__ = (
        Index("idx_thinking_sessions_status", "status"),
        Index("idx_thinking_sessions_updated", "updated_at"),
        Index("idx_thinking_sessions_type", "session_type"),
    )

    title: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    session_type: str = Field(
        default="canvas",
        sa_column=Column(String(32), nullable=False, server_default="canvas"),
    )
    status: str = Field(
        default="draft",
        sa_column=Column(String(32), nullable=False, server_default="draft"),
    )
    blocks: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False, server_default="[]"))
    tags: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False, server_default="[]"))
    topic: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    source_input: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    pinned: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    active_lens: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    note_id: str | None = Field(default=None, sa_column=Column(String(96), nullable=True, index=True))
    model_id: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))


class AgentMessageRow(Model, table=True):
    """A single message in an agent chat thread.

    ┌──────────────────────────────────────────────┐
    │  AgentMessageRow                             │
    │  role: user | assistant                      │
    │  content: markdown text                      │
    │  tool_calls: [{tool, args, result}]          │
    │  artifacts: [{type, action, id, title, ...}] │
    │  related_cards: [{zettel_id, title, reason}] │
    │  gaps: [{concept, description, confidence}]  │
    └──────────────────────────────────────────────┘
    """

    __tablename__ = "agent_messages"
    __table_args__ = (
        Index("idx_agent_messages_thread", "thread_id"),
        Index("idx_agent_messages_thread_created", "thread_id", "created_at"),
    )

    thread_id: int = Field(
        sa_column=Column(Integer, ForeignKey("thinking_sessions.id", ondelete="CASCADE"), nullable=False)
    )
    role: str = Field(sa_column=Column(String(16), nullable=False))
    content: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    tool_calls: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    artifacts: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    related_cards: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    gaps: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    active_lens: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    model_used: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    token_count: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))


__all__ = ["ThinkingSessionRow", "AgentMessageRow"]
