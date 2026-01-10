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
    """Return built-in templates for the system design starter flow.

    Templates ship as Mermaid definitions stored in Excalidraw metadata. The
    frontend converts Mermaid → Excalidraw elements for a fast, editable start.
    """

    def template(
        *,
        template_id: str,
        name: str,
        description: str,
        mermaid: str | None = None,
        components: list[str] | None = None,
    ) -> TemplateDefinition:
        metadata: dict[str, Any] = {"template": template_id}
        if mermaid:
            metadata["mermaid"] = mermaid.strip()
        return TemplateDefinition(
            id=template_id,
            name=name,
            description=description,
            components=components or [],
            diagram=_blank_diagram(metadata=metadata),
        )

    return [
        template(
            template_id="blank",
            name="Blank canvas",
            description="Start from scratch.",
        ),
        template(
            template_id="web-service",
            name="Web service (basic)",
            description="Client → load balancer → service → database (+ optional cache).",
            components=["client", "load-balancer", "service", "database", "cache"],
            mermaid="""\
flowchart LR
  Client[Client] --> LB[Load balancer]
  LB --> API[API service]
  API --> Cache[(Cache)]
  API --> DB[(Database)]
""",
        ),
        template(
            template_id="url-shortener",
            name="URL shortener",
            description="Write path + read-through cache + analytics queue.",
            components=["client", "api-gateway", "service", "cache", "database", "queue"],
            mermaid="""\
flowchart LR
  Client[Client] --> API[API]
  API --> Cache[(Cache)]
  API --> DB[(Short URL DB)]
  API --> Q[(Queue)]
  Q --> Worker[Analytics worker]
  Worker --> Analytics[(Analytics DB)]
""",
        ),
        template(
            template_id="chat",
            name="Chat / messaging",
            description="WebSocket gateway, message store, fanout, and notifications.",
            components=["client", "api-gateway", "service", "database", "queue"],
            mermaid="""\
flowchart LR
  Client[Client] --> WS[WebSocket gateway]
  WS --> Chat[Chat service]
  Chat --> MsgDB[(Message DB)]
  Chat --> Fanout[(Fanout queue)]
  Fanout --> Push[Push worker]
  Push --> APNS[APNs/FCM]
""",
        ),
        template(
            template_id="news-feed",
            name="News feed (fanout on write)",
            description="User posts enqueue fanout to per-user timelines.",
            components=["client", "service", "queue", "database", "cache"],
            mermaid="""\
flowchart LR
  Client[Client] --> API[Feed API]
  API --> PostDB[(Posts DB)]
  API --> Q[(Fanout queue)]
  Q --> Fanout[Fanout workers]
  Fanout --> TLDB[(Timeline store)]
  API --> Cache[(Timeline cache)]
  Cache --> Client
""",
        ),
        template(
            template_id="file-storage",
            name="File storage + CDN",
            description="Metadata DB, object storage, and CDN distribution.",
            components=["client", "service", "storage", "database", "cdn"],
            mermaid="""\
flowchart LR
  Client[Client] --> API[Upload API]
  API --> Meta[(Metadata DB)]
  API --> Store[(Object storage)]
  Store --> CDN[CDN]
  CDN --> Client
""",
        ),
        template(
            template_id="video-streaming",
            name="Video streaming pipeline",
            description="Upload → transcode → origin → CDN playback.",
            components=["client", "service", "queue", "storage", "cdn"],
            mermaid="""\
flowchart LR
  Client[Client] --> Upload[Upload API]
  Upload --> Raw[(Raw storage)]
  Upload --> Q[(Transcode queue)]
  Q --> Transcode[Transcode workers]
  Transcode --> Enc[(Encoded storage)]
  Enc --> Origin[Origin]
  Origin --> CDN[CDN]
  CDN --> Client
""",
        ),
        template(
            template_id="notifications",
            name="Notifications system",
            description="Event ingestion, preference store, and multi-channel delivery.",
            components=["service", "queue", "database"],
            mermaid="""\
flowchart LR
  App[App services] --> Q[(Events queue)]
  Q --> Router[Notification router]
  Router --> Pref[(Preferences DB)]
  Router --> Email[Email worker]
  Router --> SMS[SMS worker]
  Router --> Push[Push worker]
""",
        ),
        template(
            template_id="search",
            name="Search + indexing",
            description="Write to DB, stream changes, build and query an index.",
            components=["service", "database", "queue"],
            mermaid="""\
flowchart LR
  Client[Client] --> API[Search API]
  API --> Index[(Search index)]
  API --> DB[(Primary DB)]
  DB --> Stream[(Change stream)]
  Stream --> Indexer[Indexer]
  Indexer --> Index
""",
        ),
        template(
            template_id="rate-limited-api",
            name="Rate-limited API",
            description="API gateway + rate limiter backed by Redis.",
            components=["client", "api-gateway", "cache", "service"],
            mermaid="""\
flowchart LR
  Client[Client] --> GW[API gateway]
  GW --> RL[(Rate limiter / Redis)]
  GW --> Svc[Service]
""",
        ),
        template(
            template_id="checkout",
            name="E-commerce checkout",
            description="Orders, payment provider, inventory reservation, and async fulfillment.",
            components=["client", "service", "database", "queue"],
            mermaid="""\
flowchart LR
  Client[Client] --> Checkout[Checkout service]
  Checkout --> Orders[(Orders DB)]
  Checkout --> Pay[Payment provider]
  Checkout --> Q[(Fulfillment queue)]
  Q --> Fulfill[Fulfillment worker]
  Fulfill --> Inventory[(Inventory DB)]
""",
        ),
        template(
            template_id="analytics-pipeline",
            name="Analytics pipeline",
            description="Event ingestion, stream processing, and warehouse load.",
            components=["client", "queue", "storage"],
            mermaid="""\
flowchart LR
  Client[Client] --> Ingest[Ingestion API]
  Ingest --> Kafka[(Event log)]
  Kafka --> Proc[Stream processor]
  Proc --> Warehouse[(Data warehouse)]
""",
        ),
        template(
            template_id="pubsub",
            name="Pub/Sub fanout",
            description="Producers publish to a topic; multiple consumers subscribe.",
            components=["queue"],
            mermaid="""\
flowchart LR
  A[Producer A] --> Topic[(Topic)]
  B[Producer B] --> Topic
  Topic --> C1[Consumer 1]
  Topic --> C2[Consumer 2]
  Topic --> C3[Consumer 3]
""",
        ),
        template(
            template_id="microservices-gateway",
            name="Microservices behind API gateway",
            description="Gateway routes to multiple services with shared auth.",
            components=["api-gateway", "service", "database"],
            mermaid="""\
flowchart LR
  Client[Client] --> GW[API gateway]
  GW --> Auth[Auth service]
  GW --> Users[Users service]
  GW --> Billing[Billing service]
  Users --> UDB[(Users DB)]
  Billing --> BDB[(Billing DB)]
""",
        ),
        template(
            template_id="cache-aside",
            name="Cache-aside reads",
            description="Service reads cache first, falls back to DB, then populates cache.",
            components=["service", "cache", "database"],
            mermaid="""\
flowchart LR
  Client[Client] --> API[Service]
  API --> Cache[(Cache)]
  Cache --> API
  API --> DB[(Database)]
  DB --> API
""",
        ),
        template(
            template_id="event-sourcing",
            name="Event sourcing",
            description="Commands append events; projectors build read models.",
            components=["service", "database", "queue"],
            mermaid="""\
flowchart LR
  Client[Client] --> Cmd[Command service]
  Cmd --> ES[(Event store)]
  ES --> Bus[(Event bus)]
  Bus --> Proj[Projector]
  Proj --> Read[(Read model)]
  Client --> Query[Query API]
  Query --> Read
""",
        ),
    ]
