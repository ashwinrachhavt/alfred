"""Schemas for system design whiteboard sessions and analysis."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from alfred.schemas.interview_prep import LikelyQuestion, TechnicalTopic


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

    elements: List[Dict[str, Any]] = Field(default_factory=list)
    app_state: Dict[str, Any] = Field(default_factory=dict, alias="appState")
    files: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ComponentDefinition(BaseModel):
    id: str
    name: str
    category: ComponentCategory
    description: str
    default_element: Dict[str, Any]


class TemplateDefinition(BaseModel):
    id: str
    name: str
    description: str
    components: List[str] = Field(default_factory=list)
    diagram: ExcalidrawData


class DiagramVersion(BaseModel):
    id: str
    created_at: datetime
    label: Optional[str] = None
    diagram: ExcalidrawData


class DiagramExport(BaseModel):
    id: str
    format: str
    created_at: datetime
    storage_url: Optional[str] = None
    notes: Optional[str] = None


class SystemDesignArtifacts(BaseModel):
    learning_topic_ids: List[int] = Field(default_factory=list)
    learning_resource_ids: List[int] = Field(default_factory=list)
    zettel_card_ids: List[int] = Field(default_factory=list)
    interview_prep_id: Optional[str] = None
    published_at: Optional[datetime] = None


class SystemDesignSessionCreate(BaseModel):
    title: Optional[str] = None
    problem_statement: str
    template_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SystemDesignSession(BaseModel):
    id: str
    share_id: str
    title: Optional[str] = None
    problem_statement: str
    template_id: Optional[str] = None
    notes_markdown: Optional[str] = None
    diagram: ExcalidrawData
    versions: List[DiagramVersion] = Field(default_factory=list)
    exports: List[DiagramExport] = Field(default_factory=list)
    artifacts: SystemDesignArtifacts = Field(default_factory=SystemDesignArtifacts)
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AutosaveRequest(BaseModel):
    diagram: ExcalidrawData
    label: Optional[str] = None


class SystemDesignSessionUpdate(BaseModel):
    title: Optional[str] = None
    problem_statement: Optional[str] = None



class SystemDesignNotesUpdate(BaseModel):
    notes_markdown: str


class DesignPrompt(BaseModel):
    problem: str
    constraints: List[str] = Field(default_factory=list)
    target_scale: Optional[str] = None


class InvalidConnection(BaseModel):
    source: str
    target: str
    reason: str


class DiagramAnalysis(BaseModel):
    detected_components: List[str] = Field(default_factory=list)
    missing_components: List[str] = Field(default_factory=list)
    invalid_connections: List[InvalidConnection] = Field(default_factory=list)
    bottlenecks: List[str] = Field(default_factory=list)
    best_practices_hints: List[str] = Field(default_factory=list)
    completeness_score: int = Field(ge=0, le=100, default=0)
    scale_notes: List[str] = Field(default_factory=list)


class DiagramQuestion(BaseModel):
    id: str
    text: str
    rationale: Optional[str] = None


class DiagramQuestionSet(BaseModel):
    items: List[DiagramQuestion] = Field(default_factory=list)


class DiagramSuggestion(BaseModel):
    id: str
    text: str
    priority: str = "medium"


class DiagramSuggestionSet(BaseModel):
    items: List[DiagramSuggestion] = Field(default_factory=list)


class DiagramEvaluation(BaseModel):
    completeness: int = Field(ge=0, le=100, default=0)
    scalability: int = Field(ge=0, le=100, default=0)
    tradeoffs: int = Field(ge=0, le=100, default=0)
    communication: int = Field(ge=0, le=100, default=0)
    technical_depth: int = Field(ge=0, le=100, default=0)
    notes: List[str] = Field(default_factory=list)


class SystemDesignKnowledgeTopic(BaseModel):
    title: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class SystemDesignZettelDraft(BaseModel):
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    topic: Optional[str] = None


class SystemDesignInterviewPrepDraft(BaseModel):
    likely_questions: List[LikelyQuestion] = Field(default_factory=list)
    technical_topics: List[TechnicalTopic] = Field(default_factory=list)


class SystemDesignKnowledgeDraft(BaseModel):
    topics: List[SystemDesignKnowledgeTopic] = Field(default_factory=list)
    zettels: List[SystemDesignZettelDraft] = Field(default_factory=list)
    interview_prep: SystemDesignInterviewPrepDraft = Field(
        default_factory=SystemDesignInterviewPrepDraft
    )
    notes: List[str] = Field(default_factory=list)


class SystemDesignPublishRequest(BaseModel):
    create_learning_topics: bool = True
    create_zettels: bool = True
    create_interview_prep_items: bool = False
    learning_topic_id: Optional[int] = None
    interview_prep_id: Optional[str] = None
    topic_title: Optional[str] = None
    topic_tags: List[str] = Field(default_factory=list)
    zettel_tags: List[str] = Field(default_factory=list)


class SystemDesignPublishResponse(BaseModel):
    session: SystemDesignSession
    artifacts: SystemDesignArtifacts
    knowledge_draft: SystemDesignKnowledgeDraft


class DiagramExportRequest(BaseModel):
    format: str
    storage_url: Optional[str] = None
    notes: Optional[str] = None


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
