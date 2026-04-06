"""Document asset model — stores downloaded images from captured pages.

Follows the NoteAssetRow pattern: binary data in Postgres for simplicity.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DocumentAssetRow(SQLModel, table=True):
    """A binary asset (image) downloaded from a captured page.

    When a page is captured with markdown containing image URLs, a background
    task downloads the images and stores them here. The markdown is then
    rewritten to point to local asset serving endpoints so the knowledge
    persists even if the original source disappears.
    """

    __tablename__ = "document_assets"
    __table_args__ = (
        sa.Index("ix_document_assets_doc_id", "doc_id"),
        sa.Index("ix_document_assets_created_at", "created_at"),
        {"extend_existing": True},
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    doc_id: uuid.UUID = Field(
        sa_column=sa.Column(
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    original_url: str = Field(
        sa_column=sa.Column(sa.Text, nullable=False),
    )
    file_name: str = Field(
        sa_column=sa.Column(sa.String(length=500), nullable=False),
    )
    mime_type: str = Field(
        sa_column=sa.Column(sa.String(length=200), nullable=False),
    )
    size_bytes: int = Field(
        sa_column=sa.Column(sa.Integer, nullable=False),
    )
    sha256: str | None = Field(
        default=None,
        sa_column=sa.Column(sa.String(length=64)),
    )
    data: bytes = Field(
        sa_column=sa.Column(sa.LargeBinary, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=sa.Column(
            sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


__all__ = ["DocumentAssetRow"]
