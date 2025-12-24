from __future__ import annotations

import datetime as dt
from typing import Optional

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
