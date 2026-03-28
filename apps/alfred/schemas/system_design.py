"""Schemas for system design whiteboard sessions and analysis."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ComponentCategory(str, Enum):
    load_balancer = "load_balancer"
    cache = "cache"
    database = "database"
    message_queue = "message_queue"
    api_gateway = "api_gateway"
    cdn = "cdn"
    microservice = "microservice"
    storage = "storage"
    client = "client"
    other = "other"


class ExcalidrawData(BaseModel):
    """Minimal Excalidraw payload for persistence and analysis."""

    model_config = ConfigDict(validate_by_name=True)

    elements: list[dict[str, Any]] = Field(default_factory=list)
    app_state: dict[str, Any] = Field(default_factory=dict, alias="appState")
    files: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComponentDefinition(BaseModel):
    id: str
    name: str
    category: ComponentCategory
    description: str
    default_element: dict[str, Any]


class TemplateDefinition(BaseModel):
    id: str
    name: str
    description: str
    components: list[str] = Field(default_factory=list)
    diagram: ExcalidrawData


class SystemDesignShareSettings(BaseModel):
    """Public share settings for a system design session.

    Notes:
    - We intentionally do not expose password hashes/salts.
    - `has_password` is a hint for the UI to prompt for a password on shared views.
    """

    enabled: bool = True
    expires_at: datetime | None = None
    has_password: bool = False


class DiagramVersion(BaseModel):
    id: str
    created_at: datetime
    label: str | None = None
    diagram: ExcalidrawData


class DiagramExport(BaseModel):
    id: str
    format: str
    created_at: datetime
    storage_url: str | None = None
    notes: str | None = None


class SystemDesignArtifacts(BaseModel):
    learning_topic_ids: list[int] = Field(default_factory=list)
    learning_resource_ids: list[int] = Field(default_factory=list)
    zettel_card_ids: list[int] = Field(default_factory=list)
    published_at: datetime | None = None


class SystemDesignSessionCreate(BaseModel):
    title: str | None = None
    problem_statement: str
    template_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SystemDesignSession(BaseModel):
    id: str
    share_id: str
    share_settings: SystemDesignShareSettings = Field(default_factory=SystemDesignShareSettings)
    title: str | None = None
    problem_statement: str
    template_id: str | None = None
    notes_markdown: str | None = None
    diagram: ExcalidrawData
    version: int = 1
    versions: list[DiagramVersion] = Field(default_factory=list)
    exports: list[DiagramExport] = Field(default_factory=list)
    artifacts: SystemDesignArtifacts = Field(default_factory=SystemDesignArtifacts)
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutosaveRequest(BaseModel):
    diagram: ExcalidrawData
    label: str | None = None
    expected_version: int | None = None


class SystemDesignSessionSummary(BaseModel):
    id: str
    share_id: str
    title: str | None = None
    problem_statement: str
    template_id: str | None = None
    version: int = 1
    created_at: datetime
    updated_at: datetime


class SystemDesignSessionUpdate(BaseModel):
    title: str | None = None
    problem_statement: str | None = None


class SystemDesignNotesUpdate(BaseModel):
    notes_markdown: str


class SystemDesignShareUpdate(BaseModel):
    enabled: bool | None = None
    expires_at: datetime | None = None
    password: str | None = None
    clear_password: bool = False
    rotate_share_id: bool = False


class DesignPrompt(BaseModel):
    problem: str
    constraints: list[str] = Field(default_factory=list)
    target_scale: str | None = None


class InvalidConnection(BaseModel):
    source: str
    target: str
    reason: str


class DiagramAnalysis(BaseModel):
    detected_components: list[str] = Field(default_factory=list)
    missing_components: list[str] = Field(default_factory=list)
    invalid_connections: list[InvalidConnection] = Field(default_factory=list)
    bottlenecks: list[str] = Field(default_factory=list)
    best_practices_hints: list[str] = Field(default_factory=list)
    completeness_score: int = Field(ge=0, le=100, default=0)
    scale_notes: list[str] = Field(default_factory=list)


class DiagramQuestion(BaseModel):
    id: str
    text: str
    rationale: str | None = None


class DiagramQuestionSet(BaseModel):
    items: list[DiagramQuestion] = Field(default_factory=list)


class DiagramSuggestion(BaseModel):
    id: str
    text: str
    priority: str = "medium"


class DiagramSuggestionSet(BaseModel):
    items: list[DiagramSuggestion] = Field(default_factory=list)


class DiagramEvaluation(BaseModel):
    completeness: int = Field(ge=0, le=100, default=0)
    scalability: int = Field(ge=0, le=100, default=0)
    tradeoffs: int = Field(ge=0, le=100, default=0)
    communication: int = Field(ge=0, le=100, default=0)
    technical_depth: int = Field(ge=0, le=100, default=0)
    notes: list[str] = Field(default_factory=list)


class SystemDesignKnowledgeTopic(BaseModel):
    title: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class SystemDesignZettelDraft(BaseModel):
    title: str
    summary: str | None = None
    content: str | None = None
    tags: list[str] = Field(default_factory=list)
    topic: str | None = None


class SystemDesignKnowledgeDraft(BaseModel):
    topics: list[SystemDesignKnowledgeTopic] = Field(default_factory=list)
    zettels: list[SystemDesignZettelDraft] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SystemDesignPublishRequest(BaseModel):
    create_learning_topics: bool = True
    create_zettels: bool = True
    learning_topic_id: int | None = None
    topic_title: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    zettel_tags: list[str] = Field(default_factory=list)


class SystemDesignPublishResponse(BaseModel):
    session: SystemDesignSession
    artifacts: SystemDesignArtifacts
    knowledge_draft: SystemDesignKnowledgeDraft


class DiagramExportRequest(BaseModel):
    format: str
    storage_url: str | None = None
    notes: str | None = None


class SystemDesignTemplateCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(default="")
    components: list[str] = Field(default_factory=list)
    diagram: ExcalidrawData


class ScaleEstimateRequest(BaseModel):
    qps: float = Field(gt=0)
    avg_request_kb: float = Field(gt=0)
    avg_response_kb: float = Field(gt=0)
    write_percentage: float = Field(ge=0, le=100, default=20)
    storage_per_write_kb: float = Field(gt=0, default=2)
    retention_days: int = Field(gt=0, default=30)
    replication_factor: int = Field(ge=1, default=3)


class ScaleEstimateResponse(BaseModel):
    inbound_mbps: float
    outbound_mbps: float
    writes_per_day: int
    storage_gb_per_day: float
    retained_storage_gb: float
