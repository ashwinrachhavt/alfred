from __future__ import annotations

import datetime as dt
import uuid
from typing import Optional

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel


class OutreachRun(SQLModel, table=True):
    __tablename__ = "outreach_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.utcnow())
    company: str = Field(index=True, max_length=255)
    source: str = Field(max_length=32)
    count: int = Field(default=0)


class OutreachContact(SQLModel, table=True):
    __tablename__ = "outreach_contacts"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="outreach_runs.id", index=True)
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.utcnow())
    company: str = Field(index=True, max_length=255)
    name: str = Field(default="", max_length=255)
    title: str = Field(default="", max_length=255)
    email: str = Field(default="", max_length=255, index=True)
    confidence: float = Field(default=0.0)
    source: str = Field(default="", max_length=32, index=True)


class OutreachMessage(SQLModel, table=True):
    __tablename__ = "outreach_messages"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.utcnow())
    sent_at: dt.datetime | None = Field(default=None)

    company: str = Field(index=True, max_length=255)
    contact_email: str = Field(index=True, max_length=255)
    contact_name: str = Field(default="", max_length=255)
    contact_title: str = Field(default="", max_length=255)

    subject: str = Field(max_length=255)
    body: str = Field(sa_column=Column(Text()))

    provider: str = Field(default="smtp", max_length=64, index=True)
    provider_message_id: str | None = Field(default=None, max_length=128)
    status: str = Field(default="queued", max_length=32, index=True)
    error_message: str | None = Field(default=None, sa_column=Column(Text()))
    meta: dict | None = Field(default=None, sa_column=Column("metadata", JSON))
