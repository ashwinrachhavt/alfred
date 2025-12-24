"""Postgres-backed generic document store to replace Mongo collections."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from alfred.core.utils import utcnow as _utcnow


class DataStoreRow(SQLModel, table=True):
    """Generic JSON document stored per logical collection."""

    __tablename__ = "datastore_docs"
    __table_args__ = (
        sa.UniqueConstraint("collection", "doc_id", name="uq_datastore_docs_collection_doc_id"),
        sa.Index("ix_datastore_docs_collection", "collection"),
        sa.Index("ix_datastore_docs_data_gin", "data", postgresql_using="gin"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    collection: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    doc_id: str = Field(sa_column=sa.Column(sa.String(length=96), nullable=False))
    data: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=sa.Column(sa.JSON, nullable=False, server_default=sa.text("'{}'")),
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=sa.Column(
            sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=sa.Column(
            sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


__all__ = ["DataStoreRow"]
