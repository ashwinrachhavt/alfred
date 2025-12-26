"""add whiteboard tables for collaborative canvas"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f5a2d8f4cba"
down_revision: Union[str, None] = "f2b7d6c2a1ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "whiteboards",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("org_id", sa.String(length=128), nullable=True),
        sa.Column("template_id", sa.String(length=128), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_whiteboards_org_id", "whiteboards", ["org_id"], unique=False)
    op.create_index("ix_whiteboards_archived", "whiteboards", ["is_archived"], unique=False)

    op.create_table(
        "whiteboard_revisions",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("whiteboard_id", sa.Integer(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("scene_json", sa.JSON(), nullable=False),
        sa.Column("ai_context", sa.JSON(), nullable=True),
        sa.Column("applied_prompt", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["whiteboard_id"], ["whiteboards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_whiteboard_revisions_board_rev",
        "whiteboard_revisions",
        ["whiteboard_id", "revision_no"],
        unique=True,
    )
    op.create_index(
        "ix_whiteboard_revisions_board",
        "whiteboard_revisions",
        ["whiteboard_id"],
        unique=False,
    )

    op.create_table(
        "whiteboard_comments",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("whiteboard_id", sa.Integer(), nullable=False),
        sa.Column("element_id", sa.String(length=128), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["whiteboard_id"], ["whiteboards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_whiteboard_comments_board",
        "whiteboard_comments",
        ["whiteboard_id"],
        unique=False,
    )
    op.create_index(
        "ix_whiteboard_comments_element",
        "whiteboard_comments",
        ["element_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_whiteboard_comments_element", table_name="whiteboard_comments")
    op.drop_index("ix_whiteboard_comments_board", table_name="whiteboard_comments")
    op.drop_table("whiteboard_comments")
    op.drop_index("ix_whiteboard_revisions_board", table_name="whiteboard_revisions")
    op.drop_index("ix_whiteboard_revisions_board_rev", table_name="whiteboard_revisions")
    op.drop_table("whiteboard_revisions")
    op.drop_index("ix_whiteboards_archived", table_name="whiteboards")
    op.drop_index("ix_whiteboards_org_id", table_name="whiteboards")
    op.drop_table("whiteboards")
