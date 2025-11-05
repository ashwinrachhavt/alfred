"""ORM models describing Alfred's core data structures."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from alfred.core.database import Base

DEFAULT_USER_KEY = "default"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    threads: Mapped[list["EmailThread"]] = relationship(back_populates="user")
    prompt_memories: Mapped[list["PromptMemory"]] = relationship(back_populates="user")


class EmailThread(Base):
    __tablename__ = "email_threads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    external_thread_id: Mapped[str] = mapped_column(String(128))  # e.g. Gmail thread ID
    last_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped[User] = relationship(back_populates="threads")
    actions: Mapped[list["EmailAction"]] = relationship(back_populates="thread")


Index("ix_email_threads_user_external", EmailThread.user_id, EmailThread.external_thread_id, unique=True)


class EmailAction(Base):
    __tablename__ = "email_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("email_threads.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(32))  # e.g., email, notify, question, no
    payload: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    thread: Mapped[EmailThread] = relationship(back_populates="actions")


class PromptMemory(Base):
    __tablename__ = "prompt_memories"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_prompt_memories_user_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped[User] = relationship(back_populates="prompt_memories")


class GoogleCredential(Base):
    __tablename__ = "google_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_key: Mapped[str] = mapped_column(String(64), index=True, default=DEFAULT_USER_KEY)
    credential: Mapped[dict] = mapped_column(JSON)
    scopes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    is_calendar: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


__all__ = [
    "DEFAULT_USER_KEY",
    "EmailAction",
    "EmailThread",
    "GoogleCredential",
    "PromptMemory",
    "User",
]
