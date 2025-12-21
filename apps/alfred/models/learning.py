"""Learning path optimizer models (SQLModel).

Stores learning topics, attached resources, quiz attempts, spaced-repetition
reviews, and lightweight concept graph tables for visualization.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlmodel import Field

from alfred.models.base import Model


class LearningTopic(Model, table=True):
    __tablename__ = "learning_topics"
    __table_args__ = (Index("ix_learning_topics_name", "name", unique=True),)

    name: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: str = Field(default="active", sa_column=Column(String(32), nullable=False))
    progress: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    tags: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))

    interview_at: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))
    first_learned_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime, nullable=True)
    )
    last_studied_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime, nullable=True)
    )


class LearningResource(Model, table=True):
    __tablename__ = "learning_resources"
    __table_args__ = (Index("ix_learning_resources_topic_id", "topic_id"),)

    topic_id: int = Field(
        sa_column=Column(Integer, ForeignKey("learning_topics.id"), nullable=False)
    )

    title: str | None = Field(default=None, sa_column=Column(String(512), nullable=True))
    source_url: str | None = Field(default=None, sa_column=Column(String(2048), nullable=True))
    document_id: str | None = Field(default=None, sa_column=Column(String(96), nullable=True))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    added_at: datetime = Field(
        default_factory=lambda: datetime.utcnow(), sa_column=Column(DateTime, nullable=False)
    )
    extracted_at: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))


class LearningQuiz(Model, table=True):
    __tablename__ = "learning_quizzes"
    __table_args__ = (
        Index("ix_learning_quizzes_topic_id", "topic_id"),
        Index("ix_learning_quizzes_resource_id", "resource_id"),
    )

    topic_id: int = Field(
        sa_column=Column(Integer, ForeignKey("learning_topics.id"), nullable=False)
    )
    resource_id: int | None = Field(
        default=None, sa_column=Column(Integer, ForeignKey("learning_resources.id"), nullable=True)
    )

    items: list[dict] = Field(sa_column=Column(JSON, nullable=False))


class LearningQuizAttempt(Model, table=True):
    __tablename__ = "learning_quiz_attempts"
    __table_args__ = (Index("ix_learning_quiz_attempts_quiz_id", "quiz_id"),)

    quiz_id: int = Field(
        sa_column=Column(Integer, ForeignKey("learning_quizzes.id"), nullable=False)
    )

    known: list[bool] = Field(sa_column=Column(JSON, nullable=False))
    responses: list[dict] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    score: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    submitted_at: datetime = Field(
        default_factory=lambda: datetime.utcnow(), sa_column=Column(DateTime, nullable=False)
    )


class LearningReview(Model, table=True):
    __tablename__ = "learning_reviews"
    __table_args__ = (
        Index("ix_learning_reviews_topic_id", "topic_id"),
        Index("ix_learning_reviews_due_at", "due_at"),
        Index("ix_learning_reviews_open_due", "completed_at", "due_at"),
    )

    topic_id: int = Field(
        sa_column=Column(Integer, ForeignKey("learning_topics.id"), nullable=False)
    )
    stage: int = Field(sa_column=Column(Integer, nullable=False))  # 1, 2, 3 (days: 1, 7, 30)
    iteration: int = Field(default=1, sa_column=Column(Integer, nullable=False))

    due_at: datetime = Field(sa_column=Column(DateTime, nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))
    score: float | None = Field(default=None, sa_column=Column(Float, nullable=True))

    attempt_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("learning_quiz_attempts.id"), nullable=True),
    )


class LearningEntity(Model, table=True):
    __tablename__ = "learning_entities"
    __table_args__ = (Index("ix_learning_entities_name", "name", unique=True),)

    name: str = Field(sa_column=Column(String(255), nullable=False))
    type: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))


class LearningResourceEntity(Model, table=True):
    __tablename__ = "learning_resource_entities"
    __table_args__ = (
        Index("ix_learning_resource_entities_resource_id", "resource_id"),
        Index("ix_learning_resource_entities_entity_id", "entity_id"),
        Index("ix_learning_resource_entities_unique", "resource_id", "entity_id", unique=True),
    )

    resource_id: int = Field(
        sa_column=Column(Integer, ForeignKey("learning_resources.id"), nullable=False)
    )
    entity_id: int = Field(
        sa_column=Column(Integer, ForeignKey("learning_entities.id"), nullable=False)
    )


class LearningEntityRelation(Model, table=True):
    __tablename__ = "learning_entity_relations"
    __table_args__ = (
        Index("ix_learning_entity_relations_from", "from_entity_id"),
        Index("ix_learning_entity_relations_to", "to_entity_id"),
    )

    resource_id: int | None = Field(
        default=None, sa_column=Column(Integer, ForeignKey("learning_resources.id"), nullable=True)
    )
    from_entity_id: int = Field(
        sa_column=Column(Integer, ForeignKey("learning_entities.id"), nullable=False)
    )
    to_entity_id: int = Field(
        sa_column=Column(Integer, ForeignKey("learning_entities.id"), nullable=False)
    )
    type: str = Field(default="RELATED_TO", sa_column=Column(String(64), nullable=False))
