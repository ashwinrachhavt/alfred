"""Convenient exports for writing ORM models (SQLModel)."""

from sqlmodel import Field, SQLModel

from alfred.models.base import Model, TimestampMixin
from alfred.models.company import CompanyInterviewRow
from alfred.models.doc_storage import DocChunkRow, DocumentRow, NoteRow
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
from alfred.models.mongo_store import MongoDocRow
from alfred.models.research import ResearchRun
from alfred.models.system import SystemSetting
from alfred.models.zettel import ZettelCard, ZettelLink, ZettelReview
from alfred.schemas.outreach import OutreachContact, OutreachRun

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
    "OutreachRun",
    "OutreachContact",
    "ZettelCard",
    "ZettelLink",
    "ZettelReview",
    "SQLModel",
    "Field",
    "NoteRow",
    "DocumentRow",
    "DocChunkRow",
    "MongoDocRow",
    "CompanyInterviewRow",
]
