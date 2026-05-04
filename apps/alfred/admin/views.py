"""SQLAdmin ``ModelView`` definitions for Alfred tables.

Each view declares columns for list/detail pages and groups tables by
domain category so the admin sidebar stays navigable. Columns that
store large blobs (``content``, ``embedding``, ``bloom_history``) are
kept off the list view by default to avoid expensive renders.
"""

from __future__ import annotations

from sqladmin import ModelView

from alfred.models.doc_storage import DocChunkRow, DocumentRow, QuickNoteRow
from alfred.models.document_assets import DocumentAssetRow
from alfred.models.learning import (
    LearningEntity,
    LearningQuiz,
    LearningResource,
    LearningReview,
    LearningTopic,
)
from alfred.models.notes import NoteAssetRow, NoteRow, WorkspaceRow
from alfred.models.research import ResearchRun
from alfred.models.streaming import AgentRunEventRow, AgentRunRow
from alfred.models.taxonomy import TaxonomyNodeRow
from alfred.models.thinking import AgentMessageRow, ThinkingSessionRow
from alfred.models.today import DailyEntryRow
from alfred.models.user import User
from alfred.models.whiteboard import Whiteboard
from alfred.models.zettel import ZettelCard, ZettelLink, ZettelReview, ZettelSession

# -------- Knowledge: Zettels --------------------------------------------------


class ZettelCardAdmin(ModelView, model=ZettelCard):
    name = "Zettel Card"
    name_plural = "Zettel Cards"
    category = "Knowledge"
    icon = "fa-solid fa-note-sticky"

    column_list = [
        ZettelCard.id,
        ZettelCard.title,
        ZettelCard.topic,
        ZettelCard.status,
        ZettelCard.bloom_level,
        ZettelCard.importance,
        ZettelCard.confidence,
        ZettelCard.updated_at,
    ]
    column_searchable_list = [ZettelCard.title, ZettelCard.topic, ZettelCard.tags]
    column_sortable_list = [ZettelCard.updated_at, ZettelCard.bloom_level, ZettelCard.importance]
    column_default_sort = [(ZettelCard.updated_at, True)]


class ZettelSessionAdmin(ModelView, model=ZettelSession):
    name = "Zettel Session"
    name_plural = "Zettel Sessions"
    category = "Knowledge"

    column_list = [
        ZettelSession.id,
        ZettelSession.title,
        ZettelSession.shared_topic,
        ZettelSession.card_count,
        ZettelSession.ended_at,
        ZettelSession.created_at,
    ]


class ZettelLinkAdmin(ModelView, model=ZettelLink):
    name_plural = "Zettel Links"
    category = "Knowledge"
    column_list = [
        ZettelLink.id,
        ZettelLink.from_card_id,
        ZettelLink.to_card_id,
        ZettelLink.type,
        ZettelLink.bidirectional,
    ]


class ZettelReviewAdmin(ModelView, model=ZettelReview):
    name_plural = "Zettel Reviews"
    category = "Knowledge"
    column_list = [
        ZettelReview.id,
        ZettelReview.card_id,
        ZettelReview.stage,
        ZettelReview.iteration,
        ZettelReview.due_at,
        ZettelReview.completed_at,
        ZettelReview.score,
    ]


# -------- Knowledge: Documents & Notes ----------------------------------------


class DocumentAdmin(ModelView, model=DocumentRow):
    name_plural = "Documents"
    category = "Documents"
    column_list = [
        DocumentRow.id,
        DocumentRow.title,
        DocumentRow.source_url,
        DocumentRow.created_at,
    ]
    column_searchable_list = [DocumentRow.title, DocumentRow.source_url]
    column_default_sort = [(DocumentRow.created_at, True)]


class DocChunkAdmin(ModelView, model=DocChunkRow):
    name_plural = "Document Chunks"
    category = "Documents"
    column_list = [DocChunkRow.id, DocChunkRow.doc_id, DocChunkRow.idx]


class QuickNoteAdmin(ModelView, model=QuickNoteRow):
    name_plural = "Quick Notes"
    category = "Documents"
    column_list = [QuickNoteRow.id, QuickNoteRow.created_at]


class DocumentAssetAdmin(ModelView, model=DocumentAssetRow):
    name_plural = "Document Assets"
    category = "Documents"


class WorkspaceAdmin(ModelView, model=WorkspaceRow):
    name_plural = "Workspaces"
    category = "Notes"
    column_list = [WorkspaceRow.id, WorkspaceRow.name, WorkspaceRow.created_at]


class NoteAdmin(ModelView, model=NoteRow):
    name_plural = "Notes"
    category = "Notes"
    column_list = [NoteRow.id, NoteRow.title, NoteRow.workspace_id, NoteRow.updated_at]
    column_searchable_list = [NoteRow.title]
    column_default_sort = [(NoteRow.updated_at, True)]


class NoteAssetAdmin(ModelView, model=NoteAssetRow):
    name_plural = "Note Assets"
    category = "Notes"


# -------- Learning ------------------------------------------------------------


class LearningTopicAdmin(ModelView, model=LearningTopic):
    name_plural = "Learning Topics"
    category = "Learning"
    column_list = [LearningTopic.id, LearningTopic.name, LearningTopic.created_at]


class LearningResourceAdmin(ModelView, model=LearningResource):
    name_plural = "Learning Resources"
    category = "Learning"
    column_list = [
        LearningResource.id,
        LearningResource.topic_id,
        LearningResource.document_id,
        LearningResource.added_at,
        LearningResource.extracted_at,
    ]


class LearningEntityAdmin(ModelView, model=LearningEntity):
    name_plural = "Learning Entities"
    category = "Learning"


class LearningReviewAdmin(ModelView, model=LearningReview):
    name_plural = "Learning Reviews"
    category = "Learning"


class LearningQuizAdmin(ModelView, model=LearningQuiz):
    name_plural = "Learning Quizzes"
    category = "Learning"


# -------- Thinking / Agent ----------------------------------------------------


class ThinkingSessionAdmin(ModelView, model=ThinkingSessionRow):
    name_plural = "Thinking Sessions"
    category = "Agent"
    column_list = [
        ThinkingSessionRow.id,
        ThinkingSessionRow.created_at,
        ThinkingSessionRow.updated_at,
    ]
    column_default_sort = [(ThinkingSessionRow.updated_at, True)]


class AgentMessageAdmin(ModelView, model=AgentMessageRow):
    name_plural = "Agent Messages"
    category = "Agent"


class AgentRunAdmin(ModelView, model=AgentRunRow):
    name_plural = "Agent Runs"
    category = "Agent"


class AgentRunEventAdmin(ModelView, model=AgentRunEventRow):
    name_plural = "Agent Run Events"
    category = "Agent"


# -------- Misc ---------------------------------------------------------------


class ResearchRunAdmin(ModelView, model=ResearchRun):
    name_plural = "Research Runs"
    category = "Research"


class TaxonomyNodeAdmin(ModelView, model=TaxonomyNodeRow):
    name_plural = "Taxonomy Nodes"
    category = "System"


class DailyEntryAdmin(ModelView, model=DailyEntryRow):
    name_plural = "Daily Entries"
    category = "Today"


class WhiteboardAdmin(ModelView, model=Whiteboard):
    name_plural = "Whiteboards"
    category = "Canvas"


class UserAdmin(ModelView, model=User):
    name_plural = "Users"
    category = "System"
    column_list = [
        User.id,
        User.email,
        User.full_name,
        User.is_active,
        User.is_superuser,
        User.created_at,
    ]
    column_searchable_list = [User.email, User.full_name]


ALL_VIEWS: list[type[ModelView]] = [
    ZettelCardAdmin,
    ZettelSessionAdmin,
    ZettelLinkAdmin,
    ZettelReviewAdmin,
    DocumentAdmin,
    DocChunkAdmin,
    QuickNoteAdmin,
    DocumentAssetAdmin,
    WorkspaceAdmin,
    NoteAdmin,
    NoteAssetAdmin,
    LearningTopicAdmin,
    LearningResourceAdmin,
    LearningEntityAdmin,
    LearningReviewAdmin,
    LearningQuizAdmin,
    ThinkingSessionAdmin,
    AgentMessageAdmin,
    AgentRunAdmin,
    AgentRunEventAdmin,
    ResearchRunAdmin,
    TaxonomyNodeAdmin,
    DailyEntryAdmin,
    WhiteboardAdmin,
    UserAdmin,
]
