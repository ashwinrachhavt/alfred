"""add research_agent_specs

Revision ID: k8l9m0n1o2p3
Revises: j7k8l9m0n1o2
Create Date: 2026-05-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "k8l9m0n1o2p3"
down_revision = "j7k8l9m0n1o2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_agent_specs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("instructions", sa.String(), nullable=False, server_default=""),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column(
            "tool_allowlist",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "connector_bindings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "subagents",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("owner_id", sa.String(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_research_agent_specs_slug"),
    )
    op.create_index(
        "ix_research_agent_specs_slug", "research_agent_specs", ["slug"], unique=False
    )
    op.create_index(
        "ix_research_agent_specs_name", "research_agent_specs", ["name"], unique=False
    )
    op.create_index(
        "ix_research_agent_specs_owner_id",
        "research_agent_specs",
        ["owner_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_research_agent_specs_owner_id", table_name="research_agent_specs")
    op.drop_index("ix_research_agent_specs_name", table_name="research_agent_specs")
    op.drop_index("ix_research_agent_specs_slug", table_name="research_agent_specs")
    op.drop_table("research_agent_specs")
