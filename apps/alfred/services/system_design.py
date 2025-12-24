from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from alfred.core.settings import settings
from alfred.schemas.system_design import (
    AutosaveRequest,
    ComponentDefinition,
    DesignPrompt,
    DiagramAnalysis,
    DiagramEvaluation,
    DiagramExport,
    DiagramExportRequest,
    DiagramQuestion,
    DiagramSuggestion,
    DiagramVersion,
    ExcalidrawData,
    ScaleEstimateRequest,
    ScaleEstimateResponse,
    SystemDesignArtifacts,
    SystemDesignKnowledgeDraft,
    SystemDesignSession,
    SystemDesignSessionCreate,
    TemplateDefinition,
)
from alfred.services.datastore import DataStoreService
from alfred.services.llm_service import LLMService
from alfred.services.system_design_heuristics import component_library, template_library
from alfred.services.system_design_interviewer import SystemDesignInterviewer


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class SystemDesignService:
    """Postgres-backed storage and heuristics for system design interviews."""

    collection_name: str = settings.system_design_sessions_collection
    llm_service: LLMService | None = None

    def __post_init__(self) -> None:
        self._collection = DataStoreService(default_collection=self.collection_name)
        self._interviewer = SystemDesignInterviewer(llm_service=self.llm_service)

    def ensure_indexes(self) -> None:
        return

    def component_library(self) -> List[ComponentDefinition]:
        return component_library()

    def template_library(self) -> List[TemplateDefinition]:
        return template_library()

    def present_design_problem(self, problem: str) -> DesignPrompt:
        return self._interviewer.present_design_problem(problem)

    def create_session(self, payload: SystemDesignSessionCreate) -> SystemDesignSession:
        now = _utcnow()
        share_id = _new_id()
        diagram = ExcalidrawData(elements=[], appState={}, files={}, metadata={})
        doc = {
            "share_id": share_id,
            "title": payload.title,
            "problem_statement": payload.problem_statement,
            "template_id": payload.template_id,
            "diagram": diagram.model_dump(by_alias=True),
            "versions": [],
            "exports": [],
            "artifacts": SystemDesignArtifacts().model_dump(),
            "metadata": payload.metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        doc_id = self._collection.insert_one(doc)
        return self._to_session(doc_id, doc)

    def get_session(self, session_id: str) -> Optional[SystemDesignSession]:
        doc = self._collection.find_one({"_id": session_id})
        if not doc:
            return None
        return self._to_session(str(doc["_id"]), doc)

    def get_by_share_id(self, share_id: str) -> Optional[SystemDesignSession]:
        doc = self._collection.find_one({"share_id": share_id})
        if not doc:
            return None
        return self._to_session(str(doc["_id"]), doc)

    def autosave(self, session_id: str, payload: AutosaveRequest) -> Optional[SystemDesignSession]:
        now = _utcnow()
        version = DiagramVersion(
            id=_new_id(),
            created_at=now,
            label=payload.label,
            diagram=payload.diagram,
        )
        update = {
            "diagram": payload.diagram.model_dump(by_alias=True),
            "updated_at": now,
        }
        self._collection.update_one(
            {"_id": session_id},
            {"$set": update, "$push": {"versions": version.model_dump()}},
        )
        doc = self._collection.find_one({"_id": session_id})
        if not doc:
            return None
        return self._to_session(str(doc["_id"]), doc)

    def list_versions(self, session_id: str) -> List[DiagramVersion]:
        session = self.get_session(session_id)
        if not session:
            return []
        return session.versions

    def analyze(self, diagram: ExcalidrawData) -> DiagramAnalysis:
        return self._interviewer.analyze_diagram(diagram)

    def ask_probing_questions(self, diagram: ExcalidrawData) -> List[DiagramQuestion]:
        return self._interviewer.ask_probing_questions(diagram)

    def suggest_improvements(self, diagram: ExcalidrawData) -> List[DiagramSuggestion]:
        return self._interviewer.suggest_improvements(diagram)

    def evaluate_design(self, diagram: ExcalidrawData) -> DiagramEvaluation:
        return self._interviewer.evaluate_design(diagram)

    def knowledge_draft(self, session: SystemDesignSession) -> SystemDesignKnowledgeDraft:
        return self._interviewer.knowledge_draft(session)

    def add_export(
        self, session_id: str, payload: DiagramExportRequest
    ) -> Optional[SystemDesignSession]:
        now = _utcnow()
        export = DiagramExport(
            id=_new_id(),
            format=payload.format,
            storage_url=payload.storage_url,
            notes=payload.notes,
            created_at=now,
        )
        self._collection.update_one(
            {"_id": session_id},
            {"$push": {"exports": export.model_dump()}, "$set": {"updated_at": now}},
        )
        doc = self._collection.find_one({"_id": session_id})
        if not doc:
            return None
        return self._to_session(str(doc.get("_id", session_id)), doc)

    def attach_artifacts(
        self, session_id: str, artifacts: SystemDesignArtifacts
    ) -> Optional[SystemDesignSession]:
        now = _utcnow()
        data = artifacts.model_dump()
        data["published_at"] = data.get("published_at") or now
        self._collection.update_one(
            {"_id": session_id},
            {"$set": {"artifacts": data, "updated_at": now}},
        )
        doc = self._collection.find_one({"_id": session_id})
        if not doc:
            return None
        return self._to_session(str(doc["_id"]), doc)

    def estimate_scale(self, payload: ScaleEstimateRequest) -> ScaleEstimateResponse:
        inbound_mbps = (payload.qps * payload.avg_request_kb * 8) / 1024
        outbound_mbps = (payload.qps * payload.avg_response_kb * 8) / 1024
        writes_per_day = int(payload.qps * (payload.write_percentage / 100) * 86400)
        storage_gb_per_day = (
            writes_per_day * payload.storage_per_write_kb / (1024 * 1024)
        ) * payload.replication_factor
        retained_storage_gb = storage_gb_per_day * payload.retention_days
        return ScaleEstimateResponse(
            inbound_mbps=round(inbound_mbps, 2),
            outbound_mbps=round(outbound_mbps, 2),
            writes_per_day=writes_per_day,
            storage_gb_per_day=round(storage_gb_per_day, 2),
            retained_storage_gb=round(retained_storage_gb, 2),
        )

    def _to_session(self, session_id: str, doc: Dict[str, Any]) -> SystemDesignSession:
        diagram = ExcalidrawData.model_validate(doc.get("diagram") or {})
        versions = [
            DiagramVersion.model_validate(v)
            for v in (doc.get("versions") or [])
            if isinstance(v, dict)
        ]
        exports = [
            DiagramExport.model_validate(v)
            for v in (doc.get("exports") or [])
            if isinstance(v, dict)
        ]
        artifacts = SystemDesignArtifacts.model_validate(doc.get("artifacts") or {})
        return SystemDesignSession(
            id=session_id,
            share_id=doc.get("share_id", ""),
            title=doc.get("title"),
            problem_statement=doc.get("problem_statement", ""),
            template_id=doc.get("template_id"),
            diagram=diagram,
            versions=versions,
            exports=exports,
            artifacts=artifacts,
            created_at=doc.get("created_at") or _utcnow(),
            updated_at=doc.get("updated_at") or _utcnow(),
            metadata=doc.get("metadata") or {},
        )
