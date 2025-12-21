"""Convenient exports for writing ORM models (SQLModel)."""

from sqlmodel import Field, SQLModel

from alfred.models.base import Model, TimestampMixin
from alfred.models.learning import (
    LearningEntity,
    LearningEntityRelation,
    LearningQuiz,
    LearningQuizAttempt,
    LearningResource,
    LearningResourceEntity,
    LearningReview,
    LearningTopic,
)
from alfred.models.mongo import MongoSyncLog
from alfred.models.research import ResearchRun
from alfred.models.system import SystemSetting
from alfred.models.zettel import ZettelCard, ZettelLink, ZettelReview

__all__ = [
    "Model",
    "TimestampMixin",
    "MongoSyncLog",
    "ResearchRun",
    "SystemSetting",
    "LearningTopic",
    "LearningResource",
    "LearningQuiz",
    "LearningQuizAttempt",
    "LearningReview",
    "LearningEntity",
    "LearningResourceEntity",
    "LearningEntityRelation",
    "ZettelCard",
    "ZettelLink",
    "ZettelReview",
    "SQLModel",
    "Field",
]
