"""Static libraries for the system design whiteboard.

This module intentionally avoids external dependencies and network IO. It provides
small, in-memory defaults so the UI can render a template picker and (optionally)
component palette without requiring any datastore setup.
"""

from __future__ import annotations

from typing import Any

from alfred.schemas.system_design import (
    ComponentCategory,
    ComponentDefinition,
    ExcalidrawData,
    TemplateDefinition,
)


def _blank_diagram(*, metadata: dict[str, Any] | None = None) -> ExcalidrawData:
    """Return an empty Excalidraw payload with stable keys."""

    return ExcalidrawData(
        elements=[],
        appState={},
        files={},
        metadata=metadata or {},
    )


def component_library() -> list[ComponentDefinition]:
    """Return a minimal component palette for the system design canvas."""

    # Note: `default_element` is intentionally conservative. The canvas client can
    # enrich this payload when inserting onto the board.
    return [
        ComponentDefinition(
            id="client",
            name="Client",
            category=ComponentCategory.client,
            description="Browser / mobile app / SDK making requests.",
            default_element={},
        ),
        ComponentDefinition(
            id="load-balancer",
            name="Load Balancer",
            category=ComponentCategory.load_balancer,
            description="Distributes traffic across application servers.",
            default_element={},
        ),
        ComponentDefinition(
            id="api-gateway",
            name="API Gateway",
            category=ComponentCategory.api_gateway,
            description="Single entry point for routing, auth, and throttling.",
            default_element={},
        ),
        ComponentDefinition(
            id="service",
            name="Service",
            category=ComponentCategory.microservice,
            description="Stateless application service (HTTP/gRPC).",
            default_element={},
        ),
        ComponentDefinition(
            id="cache",
            name="Cache",
            category=ComponentCategory.cache,
            description="Redis / Memcached style read-through cache.",
            default_element={},
        ),
        ComponentDefinition(
            id="database",
            name="Database",
            category=ComponentCategory.database,
            description="Primary datastore (SQL/NoSQL).",
            default_element={},
        ),
        ComponentDefinition(
            id="queue",
            name="Message Queue",
            category=ComponentCategory.message_queue,
            description="Async messaging / buffering (Kafka/SQS/RabbitMQ).",
            default_element={},
        ),
        ComponentDefinition(
            id="cdn",
            name="CDN",
            category=ComponentCategory.cdn,
            description="Edge caching for static assets and media.",
            default_element={},
        ),
    ]


def template_library() -> list[TemplateDefinition]:
    """Return a minimal set of templates for the system design starter flow."""

    return [
        TemplateDefinition(
            id="blank",
            name="Blank canvas",
            description="Start from scratch.",
            components=[],
            diagram=_blank_diagram(metadata={"template": "blank"}),
        ),
        TemplateDefinition(
            id="web-service",
            name="Web service (basic)",
            description="Client → load balancer → service → database (+ optional cache).",
            components=["client", "load-balancer", "service", "database", "cache"],
            diagram=_blank_diagram(metadata={"template": "web-service"}),
        ),
    ]
