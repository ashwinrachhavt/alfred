"""Convenient exports for writing ORM models (SQLModel)."""

from sqlmodel import Field, SQLModel

from alfred.models.base import Model, TimestampMixin
from alfred.models.company import (
    ResearchReportRow,  # DB table: research_reports
)
from alfred.models.datastore import DataStoreRow
from alfred.models.doc_storage import DocChunkRow, DocumentRow, QuickNoteRow
from alfred.models.document_assets import DocumentAssetRow
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
from alfred.models.research_agent import ResearchAgentSpecRow
from alfred.models.streaming import (
    AgentRunEventRow,
    AgentRunRow,
    AgentRunSnapshotRow,
)
from alfred.models.system import SystemSetting
from alfred.models.tasks import (
    TaskBoardRow,
    TaskCalendarEventRow,
    TaskColumnRow,
    TaskFocusSessionRow,
    TaskKnowledgeLinkRow,
    TaskLearningRow,
    TaskPomodoroSessionRow,
    TaskProjectRow,
    TaskRewardDefinitionRow,
    TaskRow,
    UserTaskGamificationProfileRow,
    UserTaskRewardProgressRow,
    UserTaskRewardRow,
)
from alfred.models.taxonomy import TaxonomyNodeRow
from alfred.models.thinking import AgentMessageRow, ThinkingSessionRow
from alfred.models.today import DailyEntryRow, DailyReflectionRow
from alfred.models.user import User
from alfred.models.whiteboard import Whiteboard, WhiteboardComment, WhiteboardRevision
from alfred.models.zettel import ZettelCard, ZettelLink, ZettelReview, ZettelSession

__all__ = [
    "Model",
    "TimestampMixin",
    "ResearchRun",
    "ResearchAgentSpecRow",
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
    "ZettelSession",
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
    "TaxonomyNodeRow",
    "ThinkingSessionRow",
    "AgentMessageRow",
    "AgentRunRow",
    "AgentRunEventRow",
    "AgentRunSnapshotRow",
    "DailyEntryRow",
    "DailyReflectionRow",
    "DocumentAssetRow",
    "TaskBoardRow",
    "TaskCalendarEventRow",
    "TaskColumnRow",
    "TaskFocusSessionRow",
    "TaskKnowledgeLinkRow",
    "TaskLearningRow",
    "TaskPomodoroSessionRow",
    "TaskProjectRow",
    "TaskRewardDefinitionRow",
    "TaskRow",
    "UserTaskGamificationProfileRow",
    "UserTaskRewardProgressRow",
    "UserTaskRewardRow",
]
