"""Convenient exports for writing ORM models (SQLModel)."""

from sqlmodel import Field, SQLModel

from alfred.models.base import Model, TimestampMixin
from alfred.models.company import (
    CompanyResearchReportRow,  # deprecated alias
    ResearchReportRow,  # DB table: research_reports
)
from alfred.models.datastore import DataStoreRow
from alfred.models.doc_storage import DocChunkRow, DocumentRow, QuickNoteRow
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
from alfred.models.notes import NoteAssetRow, NoteRow, WorkspaceRow
from alfred.models.research import ResearchRun
from alfred.models.system import SystemSetting
from alfred.models.taxonomy import TaxonomyNodeRow
from alfred.models.thinking import AgentMessageRow, ThinkingSessionRow
from alfred.models.user import User
from alfred.models.whiteboard import Whiteboard, WhiteboardComment, WhiteboardRevision
from alfred.models.zettel import ZettelCard, ZettelLink, ZettelReview

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
    "ZettelCard",
    "ZettelLink",
    "ZettelReview",
    "Whiteboard",
    "WhiteboardRevision",
    "WhiteboardComment",
    "User",
    "SQLModel",
    "Field",
    "QuickNoteRow",
    "DocumentRow",
    "DocChunkRow",
    "WorkspaceRow",
    "NoteRow",
    "NoteAssetRow",
    "DataStoreRow",
    "ResearchReportRow",
    "CompanyResearchReportRow",
    "TaxonomyNodeRow",
    "ThinkingSessionRow",
    "AgentMessageRow",
]
