"""Convenient exports for writing ORM models (SQLModel)."""

from sqlmodel import Field, SQLModel

from alfred.models.base import Model, TimestampMixin
from alfred.models.company import CompanyInterviewRow
from alfred.models.datastore import DataStoreRow
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
from alfred.models.research import ResearchRun
from alfred.models.system import SystemSetting
from alfred.models.user import User
from alfred.models.whiteboard import Whiteboard, WhiteboardComment, WhiteboardRevision
from alfred.models.zettel import ZettelCard, ZettelLink, ZettelReview
from alfred.schemas.outreach import OutreachContact, OutreachMessage, OutreachRun

__all__ = [
    "Model",
    "TimestampMixin",
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
    "OutreachMessage",
    "OutreachContact",
    "ZettelCard",
    "ZettelLink",
    "ZettelReview",
    "Whiteboard",
    "WhiteboardRevision",
    "WhiteboardComment",
    "User",
    "SQLModel",
    "Field",
    "NoteRow",
    "DocumentRow",
    "DocChunkRow",
    "DataStoreRow",
    "CompanyInterviewRow",
]
