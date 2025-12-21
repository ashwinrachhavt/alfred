from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database

from alfred.core.settings import settings
from alfred.schemas.system_design import (
    AutosaveRequest,
    ComponentCategory,
    ComponentDefinition,
    DiagramAnalysis,
    DiagramEvaluation,
    DiagramQuestion,
    DiagramSuggestion,
    DiagramVersion,
    ExcalidrawData,
    InvalidConnection,
    ScaleEstimateRequest,
    ScaleEstimateResponse,
    SystemDesignSession,
    SystemDesignSessionCreate,
    TemplateDefinition,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


def _component_name(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def _match_category(text: str) -> ComponentCategory:
    key = _component_name(text)
    if any(k in key for k in ("load balancer", "lb")):
        return ComponentCategory.load_balancer
    if any(k in key for k in ("cache", "redis", "memcached")):
        return ComponentCategory.cache
    if any(k in key for k in ("database", "postgres", "mysql", "sql", "nosql", "db")):
        return ComponentCategory.database
    if any(k in key for k in ("queue", "kafka", "rabbitmq", "sqs")):
        return ComponentCategory.message_queue
    if any(k in key for k in ("api gateway", "gateway", "edge")):
        return ComponentCategory.api_gateway
    if "cdn" in key:
        return ComponentCategory.cdn
    if any(k in key for k in ("service", "microservice", "worker")):
        return ComponentCategory.microservice
    if any(k in key for k in ("storage", "s3", "blob")):
        return ComponentCategory.storage
    if any(k in key for k in ("client", "browser", "mobile")):
        return ComponentCategory.client
    return ComponentCategory.other


def _element_label(element: Dict[str, Any]) -> Optional[str]:
    for key in ("label", "text", "name", "title"):
        value = element.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    custom = element.get("customData") or element.get("data") or {}
    if isinstance(custom, dict):
        for key in ("component", "componentType", "component_name", "componentName"):
            value = custom.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _component_library() -> List[ComponentDefinition]:
    def element(label: str, component_type: str, color: str) -> Dict[str, Any]:
        return {
            "type": "rectangle",
            "label": label,
            "style": {"strokeColor": color, "backgroundColor": "#F8FAFC"},
            "customData": {"componentType": component_type},
        }

    return [
        ComponentDefinition(
            id="load-balancer",
            name="Load Balancer",
            category=ComponentCategory.load_balancer,
            description="Distributes traffic across services.",
            default_element=element("Load Balancer", "load_balancer", "#0EA5E9"),
        ),
        ComponentDefinition(
            id="api-gateway",
            name="API Gateway",
            category=ComponentCategory.api_gateway,
            description="Edge routing, auth, and rate limiting.",
            default_element=element("API Gateway", "api_gateway", "#6366F1"),
        ),
        ComponentDefinition(
            id="microservice",
            name="Microservice",
            category=ComponentCategory.microservice,
            description="Core service container.",
            default_element=element("Service", "microservice", "#22C55E"),
        ),
        ComponentDefinition(
            id="cache",
            name="Cache (Redis/Memcached)",
            category=ComponentCategory.cache,
            description="Hot data layer.",
            default_element=element("Cache", "cache", "#F59E0B"),
        ),
        ComponentDefinition(
            id="database",
            name="Database",
            category=ComponentCategory.database,
            description="Primary data store.",
            default_element=element("Database", "database", "#A855F7"),
        ),
        ComponentDefinition(
            id="message-queue",
            name="Message Queue",
            category=ComponentCategory.message_queue,
            description="Async buffering and fanout.",
            default_element=element("Queue", "message_queue", "#F97316"),
        ),
        ComponentDefinition(
            id="cdn",
            name="CDN",
            category=ComponentCategory.cdn,
            description="Static content acceleration.",
            default_element=element("CDN", "cdn", "#38BDF8"),
        ),
        ComponentDefinition(
            id="storage",
            name="Object Storage",
            category=ComponentCategory.storage,
            description="Blob/object storage layer.",
            default_element=element("Storage", "storage", "#14B8A6"),
        ),
        ComponentDefinition(
            id="client",
            name="Client",
            category=ComponentCategory.client,
            description="Web/mobile client.",
            default_element=element("Client", "client", "#64748B"),
        ),
    ]


def _template_library() -> List[TemplateDefinition]:
    def base_diagram() -> ExcalidrawData:
        return ExcalidrawData(elements=[], appState={}, files={}, metadata={"layout": "seed"})

    return [
        TemplateDefinition(
            id="ecommerce",
            name="E-commerce",
            description="Storefront with checkout, inventory, and payments.",
            components=[
                "client",
                "cdn",
                "load-balancer",
                "api-gateway",
                "microservice",
                "cache",
                "database",
                "message-queue",
                "storage",
            ],
            diagram=base_diagram(),
        ),
        TemplateDefinition(
            id="social",
            name="Social Media",
            description="Feed, messaging, and media storage stack.",
            components=[
                "client",
                "cdn",
                "load-balancer",
                "api-gateway",
                "microservice",
                "cache",
                "database",
                "message-queue",
                "storage",
            ],
            diagram=base_diagram(),
        ),
    ]


def _required_categories() -> List[ComponentCategory]:
    return [
        ComponentCategory.load_balancer,
        ComponentCategory.api_gateway,
        ComponentCategory.microservice,
        ComponentCategory.database,
        ComponentCategory.cache,
    ]


def _allowed_connections() -> Dict[ComponentCategory, List[ComponentCategory]]:
    return {
        ComponentCategory.client: [ComponentCategory.cdn, ComponentCategory.load_balancer],
        ComponentCategory.cdn: [ComponentCategory.load_balancer, ComponentCategory.api_gateway],
        ComponentCategory.load_balancer: [
            ComponentCategory.api_gateway,
            ComponentCategory.microservice,
        ],
        ComponentCategory.api_gateway: [ComponentCategory.microservice],
        ComponentCategory.microservice: [
            ComponentCategory.cache,
            ComponentCategory.database,
            ComponentCategory.message_queue,
            ComponentCategory.storage,
        ],
        ComponentCategory.cache: [ComponentCategory.database],
        ComponentCategory.message_queue: [ComponentCategory.microservice],
    }


@dataclass
class SystemDesignService:
    """Mongo-backed storage and heuristics for system design interviews."""

    database: Database | None = None
    collection_name: str = settings.system_design_sessions_collection

    def __post_init__(self) -> None:
        if self.database is None:
            from alfred.connectors.mongo_connector import MongoConnector

            self.database = MongoConnector().database
        self._collection: Collection = self.database.get_collection(self.collection_name)

    def ensure_indexes(self) -> None:
        try:
            self._collection.create_index([("share_id", 1)], name="share_id", unique=True)
            self._collection.create_index([("updated_at", -1)], name="updated_desc")
            self._collection.create_index([("created_at", -1)], name="created_desc")
        except Exception:
            pass

    def component_library(self) -> List[ComponentDefinition]:
        return _component_library()

    def template_library(self) -> List[TemplateDefinition]:
        return _template_library()

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
            "metadata": payload.metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        res = self._collection.insert_one(doc)
        doc_id = str(res.inserted_id)
        return self._to_session(doc_id, doc)

    def get_session(self, session_id: str) -> Optional[SystemDesignSession]:
        if not ObjectId.is_valid(session_id):
            return None
        doc = self._collection.find_one({"_id": ObjectId(session_id)})
        if not doc:
            return None
        return self._to_session(str(doc["_id"]), doc)

    def get_by_share_id(self, share_id: str) -> Optional[SystemDesignSession]:
        doc = self._collection.find_one({"share_id": share_id})
        if not doc:
            return None
        return self._to_session(str(doc["_id"]), doc)

    def autosave(self, session_id: str, payload: AutosaveRequest) -> Optional[SystemDesignSession]:
        if not ObjectId.is_valid(session_id):
            return None
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
            {"_id": ObjectId(session_id)},
            {"$set": update, "$push": {"versions": version.model_dump()}},
        )
        doc = self._collection.find_one({"_id": ObjectId(session_id)})
        if not doc:
            return None
        return self._to_session(str(doc["_id"]), doc)

    def list_versions(self, session_id: str) -> List[DiagramVersion]:
        session = self.get_session(session_id)
        if not session:
            return []
        return session.versions

    def analyze(self, diagram: ExcalidrawData) -> DiagramAnalysis:
        elements = diagram.elements or []
        id_to_category: Dict[str, ComponentCategory] = {}
        detected: List[str] = []

        for element in elements:
            label = _element_label(element)
            if not label:
                continue
            category = _match_category(label)
            elem_id = element.get("id")
            if isinstance(elem_id, str) and elem_id.strip():
                id_to_category[elem_id] = category
            detected.append(label)

        missing = []
        required = _required_categories()
        present_categories = {cat for cat in id_to_category.values() if cat != ComponentCategory.other}
        for cat in required:
            if cat not in present_categories:
                missing.append(cat.value.replace("_", " ").title())

        invalid_connections: List[InvalidConnection] = []
        allowed = _allowed_connections()
        for element in elements:
            if element.get("type") not in {"arrow", "line"}:
                continue
            start = element.get("startBinding", {}) or {}
            end = element.get("endBinding", {}) or {}
            source_id = start.get("elementId")
            target_id = end.get("elementId")
            if not (isinstance(source_id, str) and isinstance(target_id, str)):
                continue
            source_cat = id_to_category.get(source_id)
            target_cat = id_to_category.get(target_id)
            if not source_cat or not target_cat:
                continue
            allowed_targets = allowed.get(source_cat, [])
            if target_cat not in allowed_targets:
                invalid_connections.append(
                    InvalidConnection(
                        source=source_cat.value,
                        target=target_cat.value,
                        reason="Unusual flow for system design components.",
                    )
                )

        bottlenecks: List[str] = []
        if ComponentCategory.load_balancer not in present_categories and len(present_categories) > 2:
            bottlenecks.append("No load balancer detected for horizontal scaling.")
        if ComponentCategory.cache not in present_categories:
            bottlenecks.append("No cache layer detected for hot data.")
        if ComponentCategory.message_queue not in present_categories:
            bottlenecks.append("No queue detected for async workloads.")

        hints: List[str] = []
        if ComponentCategory.cdn not in present_categories:
            hints.append("Consider adding a CDN for static assets.")
        if ComponentCategory.storage not in present_categories:
            hints.append("Add object storage for media or large files.")

        completeness = int((len(present_categories.intersection(set(required))) / len(required)) * 100)
        scale_notes = []
        if completeness < 60:
            scale_notes.append("Add core tiers before discussing scaling.")
        elif ComponentCategory.cache in present_categories and ComponentCategory.message_queue in present_categories:
            scale_notes.append("Layering cache and async queues improves tail latency.")

        return DiagramAnalysis(
            detected_components=detected,
            missing_components=missing,
            invalid_connections=invalid_connections,
            bottlenecks=bottlenecks,
            best_practices_hints=hints,
            completeness_score=completeness,
            scale_notes=scale_notes,
        )

    def ask_probing_questions(self, diagram: ExcalidrawData) -> List[DiagramQuestion]:
        analysis = self.analyze(diagram)
        questions: List[DiagramQuestion] = []
        if analysis.missing_components:
            questions.append(
                DiagramQuestion(
                    id=_new_id(),
                    text="How will requests be balanced and routed across your services?",
                    rationale="Missing a clear traffic distribution layer.",
                )
            )
        questions.append(
            DiagramQuestion(
                id=_new_id(),
                text="What data consistency trade-offs are acceptable for this system?",
                rationale="Clarifies replication and caching strategy.",
            )
        )
        if not analysis.detected_components:
            questions.append(
                DiagramQuestion(
                    id=_new_id(),
                    text="Start with the client entrypoint. What is the first component a request hits?",
                )
            )
        return questions

    def suggest_improvements(self, diagram: ExcalidrawData) -> List[DiagramSuggestion]:
        analysis = self.analyze(diagram)
        suggestions: List[DiagramSuggestion] = []
        for missing in analysis.missing_components:
            suggestions.append(
                DiagramSuggestion(
                    id=_new_id(),
                    text=f"Add a {missing.lower()} layer to improve completeness.",
                    priority="high",
                )
            )
        for hint in analysis.best_practices_hints:
            suggestions.append(DiagramSuggestion(id=_new_id(), text=hint, priority="medium"))
        if analysis.invalid_connections:
            suggestions.append(
                DiagramSuggestion(
                    id=_new_id(),
                    text="Review component connections for logical request flow.",
                    priority="medium",
                )
            )
        return suggestions

    def evaluate_design(self, diagram: ExcalidrawData) -> DiagramEvaluation:
        analysis = self.analyze(diagram)
        completeness = analysis.completeness_score
        scalability = min(100, completeness + (10 if analysis.bottlenecks == [] else 0))
        tradeoffs = 70 if analysis.detected_components else 30
        communication = 75 if diagram.elements else 40
        technical_depth = min(100, 50 + len(analysis.detected_components) * 5)
        notes = analysis.bottlenecks + analysis.best_practices_hints
        return DiagramEvaluation(
            completeness=completeness,
            scalability=scalability,
            tradeoffs=tradeoffs,
            communication=communication,
            technical_depth=technical_depth,
            notes=notes,
        )

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
        return SystemDesignSession(
            id=session_id,
            share_id=doc.get("share_id", ""),
            title=doc.get("title"),
            problem_statement=doc.get("problem_statement", ""),
            template_id=doc.get("template_id"),
            diagram=diagram,
            versions=versions,
            created_at=doc.get("created_at") or _utcnow(),
            updated_at=doc.get("updated_at") or _utcnow(),
            metadata=doc.get("metadata") or {},
        )
