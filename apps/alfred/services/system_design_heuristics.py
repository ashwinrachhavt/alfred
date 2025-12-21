from __future__ import annotations

from typing import Any, Dict, List, Optional

from alfred.schemas.interview_prep import LikelyQuestion, TechnicalTopic
from alfred.schemas.system_design import (
    ComponentCategory,
    ComponentDefinition,
    DiagramAnalysis,
    DiagramEvaluation,
    DiagramQuestion,
    DiagramSuggestion,
    ExcalidrawData,
    InvalidConnection,
    SystemDesignKnowledgeDraft,
    SystemDesignKnowledgeTopic,
    SystemDesignInterviewPrepDraft,
    SystemDesignZettelDraft,
    TemplateDefinition,
)


def _component_name(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def match_category(text: str) -> ComponentCategory:
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


def element_label(element: Dict[str, Any]) -> Optional[str]:
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


def component_library() -> List[ComponentDefinition]:
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


def template_library() -> List[TemplateDefinition]:
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


def summarize_diagram(diagram: ExcalidrawData) -> dict[str, Any]:
    elements = diagram.elements or []
    id_to_category: Dict[str, ComponentCategory] = {}
    labels: List[str] = []
    for element in elements:
        label = element_label(element)
        if not label:
            continue
        category = match_category(label)
        elem_id = element.get("id")
        if isinstance(elem_id, str) and elem_id.strip():
            id_to_category[elem_id] = category
        labels.append(label)
    edges = []
    for element in elements:
        if element.get("type") not in {"arrow", "line"}:
            continue
        start = element.get("startBinding", {}) or {}
        end = element.get("endBinding", {}) or {}
        source_id = start.get("elementId")
        target_id = end.get("elementId")
        if not (isinstance(source_id, str) and isinstance(target_id, str)):
            continue
        edges.append({"source": source_id, "target": target_id})
    return {
        "labels": labels,
        "id_to_category": id_to_category,
        "edges": edges,
    }


def analyze_diagram(diagram: ExcalidrawData) -> DiagramAnalysis:
    summary = summarize_diagram(diagram)
    id_to_category: Dict[str, ComponentCategory] = summary["id_to_category"]
    detected = summary["labels"]

    required = [
        ComponentCategory.load_balancer,
        ComponentCategory.api_gateway,
        ComponentCategory.microservice,
        ComponentCategory.database,
        ComponentCategory.cache,
    ]
    present_categories = {cat for cat in id_to_category.values() if cat != ComponentCategory.other}
    missing = [
        cat.value.replace("_", " ").title()
        for cat in required
        if cat not in present_categories
    ]

    allowed_connections = {
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

    invalid_connections: List[InvalidConnection] = []
    for element in diagram.elements or []:
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
        allowed_targets = allowed_connections.get(source_cat, [])
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


def ask_probing_questions(diagram: ExcalidrawData) -> List[DiagramQuestion]:
    analysis = analyze_diagram(diagram)
    questions: List[DiagramQuestion] = []
    if analysis.missing_components:
        questions.append(
            DiagramQuestion(
                id="missing-traffic",
                text="How will requests be balanced and routed across your services?",
                rationale="Missing a clear traffic distribution layer.",
            )
        )
    questions.append(
        DiagramQuestion(
            id="consistency",
            text="What data consistency trade-offs are acceptable for this system?",
            rationale="Clarifies replication and caching strategy.",
        )
    )
    if not analysis.detected_components:
        questions.append(
            DiagramQuestion(
                id="entrypoint",
                text="Start with the client entrypoint. What is the first component a request hits?",
            )
        )
    return questions


def suggest_improvements(diagram: ExcalidrawData) -> List[DiagramSuggestion]:
    analysis = analyze_diagram(diagram)
    suggestions: List[DiagramSuggestion] = []
    for missing in analysis.missing_components:
        suggestions.append(
            DiagramSuggestion(
                id=f"add-{missing.lower().replace(' ', '-')}",
                text=f"Add a {missing.lower()} layer to improve completeness.",
                priority="high",
            )
        )
    for idx, hint in enumerate(analysis.best_practices_hints, start=1):
        suggestions.append(
            DiagramSuggestion(id=f"hint-{idx}", text=hint, priority="medium")
        )
    if analysis.invalid_connections:
        suggestions.append(
            DiagramSuggestion(
                id="connections",
                text="Review component connections for logical request flow.",
                priority="medium",
            )
        )
    return suggestions


def evaluate_design(diagram: ExcalidrawData) -> DiagramEvaluation:
    analysis = analyze_diagram(diagram)
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


def knowledge_draft(diagram: ExcalidrawData, *, problem_statement: str) -> SystemDesignKnowledgeDraft:
    analysis = analyze_diagram(diagram)
    topics = []
    if problem_statement.strip():
        topics.append(
            SystemDesignKnowledgeTopic(
                title=f"System design: {problem_statement.strip()}",
                description="Core architecture overview and key trade-offs.",
                tags=["system-design", "interview"],
            )
        )
    for missing in analysis.missing_components:
        topics.append(
            SystemDesignKnowledgeTopic(
                title=f"Deep dive: {missing}",
                description=f"Study patterns for {missing.lower()} layers.",
                tags=["system-design"],
            )
        )

    zettels = []
    for label in analysis.detected_components[:12]:
        zettels.append(
            SystemDesignZettelDraft(
                title=f"{label} role and trade-offs",
                summary=f"Why {label} exists in the system and when it becomes a bottleneck.",
                content="Capture responsibilities, scaling notes, and failure modes.",
                tags=["system-design"],
                topic=problem_statement.strip() or None,
            )
        )

    return SystemDesignKnowledgeDraft(
        topics=topics,
        zettels=zettels,
        interview_prep=SystemDesignInterviewPrepDraft(
            likely_questions=[
                LikelyQuestion(
                    question="Walk me through the request flow from client to database.",
                    suggested_answer="Explain each hop, the purpose of each tier, and where scale bottlenecks appear.",
                    focus_areas=["system design", "communication"],
                ),
                LikelyQuestion(
                    question="How would you scale the busiest component in this design?",
                    suggested_answer="Discuss horizontal scaling, caching, and async processing options.",
                    focus_areas=["scalability"],
                ),
            ]
            + [
                LikelyQuestion(
                    question=f"Why did you choose to include {missing.lower()}?",
                    suggested_answer="Describe the role, trade-offs, and alternative approaches.",
                    focus_areas=["trade-offs"],
                )
                for missing in analysis.missing_components
            ],
            technical_topics=[
                TechnicalTopic(topic="Caching strategies", priority=4),
                TechnicalTopic(topic="Load balancing patterns", priority=3),
                TechnicalTopic(topic="Database sharding and replication", priority=4),
            ],
        ),
        notes=analysis.best_practices_hints,
    )
