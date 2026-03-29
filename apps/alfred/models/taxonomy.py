"""Knowledge taxonomy framework models.

Represents the hierarchical taxonomy of domains, subdomains, and microtopics
used to classify documents and learning resources across Alfred.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from alfred.core.utils import utcnow as _utcnow


class TaxonomyNodeRow(SQLModel, table=True):
    """Hierarchical taxonomy node for knowledge classification.

    Three-level hierarchy:
    - Level 1: Domain (e.g., "system-design", "ai-engineering")
    - Level 2: Subdomain (e.g., "databases", "caching")
    - Level 3: Microtopic (e.g., "redis", "postgres")
    """

    __tablename__ = "taxonomy_nodes"
    __table_args__ = (
        sa.Index("ix_taxonomy_nodes_level", "level"),
        sa.Index("ix_taxonomy_nodes_parent_slug", "parent_slug"),
    )

    id: int = Field(
        default=None,
        sa_column=sa.Column(sa.Integer, primary_key=True, autoincrement=True, nullable=False),
    )
    slug: str = Field(
        sa_column=sa.Column(sa.String(length=128), unique=True, nullable=False)
    )
    display_name: str = Field(
        sa_column=sa.Column(sa.String(length=256), nullable=False)
    )
    level: int = Field(
        sa_column=sa.Column(
            sa.SmallInteger,
            nullable=False,
            info={"check": "level between 1 and 3"},
        )
    )
    parent_slug: str | None = Field(
        default=None,
        sa_column=sa.Column(
            sa.String(length=128),
            sa.ForeignKey("taxonomy_nodes.slug", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    description: str | None = Field(
        default=None,
        sa_column=sa.Column(sa.Text, nullable=True)
    )
    sort_order: int = Field(
        default=0,
        sa_column=sa.Column(sa.Integer, nullable=False, server_default=sa.text("0"))
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


__all__ = ["TaxonomyNodeRow"]
