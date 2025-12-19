"""Relational models related to MongoDB workflows (SQLModel)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Column, String, Text
from sqlmodel import Field

from alfred.models.base import Model


class MongoSyncLog(Model, table=True):
    """Records Mongo-related operations for auditing/monitoring."""

    __tablename__ = "mongo_sync_logs"

    collection: str = Field(sa_column=Column(String(255), nullable=False))
    operation: str = Field(sa_column=Column(String(64), nullable=False))
    document_id: str | None = Field(default=None, sa_column=Column(String(96), nullable=True))
    status: str = Field(default="success", sa_column=Column(String(32), nullable=False))
    payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
