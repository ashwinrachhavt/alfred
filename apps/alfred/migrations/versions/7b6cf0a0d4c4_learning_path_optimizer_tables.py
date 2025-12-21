"""learning path optimizer tables

Revision ID: 7b6cf0a0d4c4
Revises: ec1447e7d08f
Create Date: 2025-12-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b6cf0a0d4c4"
down_revision: Union[str, None] = "ec1447e7d08f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_topics",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("interview_at", sa.DateTime(), nullable=True),
        sa.Column("first_learned_at", sa.DateTime(), nullable=True),
        sa.Column("last_studied_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_topics_name", "learning_topics", ["name"], unique=True)

    op.create_table(
        "learning_resources",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("document_id", sa.String(length=96), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.Column("extracted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["topic_id"], ["learning_topics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_resources_topic_id", "learning_resources", ["topic_id"], unique=False)

    op.create_table(
        "learning_quizzes",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["resource_id"], ["learning_resources.id"]),
        sa.ForeignKeyConstraint(["topic_id"], ["learning_topics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_quizzes_topic_id", "learning_quizzes", ["topic_id"], unique=False)
    op.create_index("ix_learning_quizzes_resource_id", "learning_quizzes", ["resource_id"], unique=False)

    op.create_table(
        "learning_quiz_attempts",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=False),
        sa.Column("known", sa.JSON(), nullable=False),
        sa.Column("responses", sa.JSON(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["quiz_id"], ["learning_quizzes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learning_quiz_attempts_quiz_id", "learning_quiz_attempts", ["quiz_id"], unique=False
    )

    op.create_table(
        "learning_reviews",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("attempt_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["attempt_id"], ["learning_quiz_attempts.id"]),
        sa.ForeignKeyConstraint(["topic_id"], ["learning_topics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_reviews_topic_id", "learning_reviews", ["topic_id"], unique=False)
    op.create_index("ix_learning_reviews_due_at", "learning_reviews", ["due_at"], unique=False)
    op.create_index(
        "ix_learning_reviews_open_due",
        "learning_reviews",
        ["completed_at", "due_at"],
        unique=False,
    )

    op.create_table(
        "learning_entities",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_entities_name", "learning_entities", ["name"], unique=True)

    op.create_table(
        "learning_resource_entities",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["learning_entities.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["learning_resources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learning_resource_entities_resource_id",
        "learning_resource_entities",
        ["resource_id"],
        unique=False,
    )
    op.create_index(
        "ix_learning_resource_entities_entity_id",
        "learning_resource_entities",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_learning_resource_entities_unique",
        "learning_resource_entities",
        ["resource_id", "entity_id"],
        unique=True,
    )

    op.create_table(
        "learning_entity_relations",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("from_entity_id", sa.Integer(), nullable=False),
        sa.Column("to_entity_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["from_entity_id"], ["learning_entities.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["learning_resources.id"]),
        sa.ForeignKeyConstraint(["to_entity_id"], ["learning_entities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learning_entity_relations_from",
        "learning_entity_relations",
        ["from_entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_learning_entity_relations_to",
        "learning_entity_relations",
        ["to_entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_learning_entity_relations_to", table_name="learning_entity_relations")
    op.drop_index("ix_learning_entity_relations_from", table_name="learning_entity_relations")
    op.drop_table("learning_entity_relations")
    op.drop_index("ix_learning_resource_entities_unique", table_name="learning_resource_entities")
    op.drop_index("ix_learning_resource_entities_entity_id", table_name="learning_resource_entities")
    op.drop_index("ix_learning_resource_entities_resource_id", table_name="learning_resource_entities")
    op.drop_table("learning_resource_entities")
    op.drop_index("ix_learning_entities_name", table_name="learning_entities")
    op.drop_table("learning_entities")
    op.drop_index("ix_learning_reviews_open_due", table_name="learning_reviews")
    op.drop_index("ix_learning_reviews_due_at", table_name="learning_reviews")
    op.drop_index("ix_learning_reviews_topic_id", table_name="learning_reviews")
    op.drop_table("learning_reviews")
    op.drop_index("ix_learning_quiz_attempts_quiz_id", table_name="learning_quiz_attempts")
    op.drop_table("learning_quiz_attempts")
    op.drop_index("ix_learning_quizzes_resource_id", table_name="learning_quizzes")
    op.drop_index("ix_learning_quizzes_topic_id", table_name="learning_quizzes")
    op.drop_table("learning_quizzes")
    op.drop_index("ix_learning_resources_topic_id", table_name="learning_resources")
    op.drop_table("learning_resources")
    op.drop_index("ix_learning_topics_name", table_name="learning_topics")
    op.drop_table("learning_topics")

