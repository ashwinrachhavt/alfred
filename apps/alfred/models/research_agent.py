"""ResearchAgentSpec — user-defined deep research agent configuration.

A spec is the persisted, serializable definition of a deep research agent.
The runtime (DeepResearchService) loads a spec by id, resolves tool names
against the tool registry, binds connector config, and passes the whole
bundle into `deepagents.create_deep_agent(...)`.

Shape lives in JSONB so users can evolve the spec without migrations.

    ┌──────────────────────┐          ┌────────────────────────┐
    │ ResearchAgentSpecRow │─ load ──▶│ DeepResearchService    │
    │  (Postgres)          │          │  build_agent(spec)     │
    └──────────────────────┘          │   └─▶ create_deep_agent│
                                      └────────────────────────┘
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from alfred.models.base import Model

# Postgres gets JSONB (indexed containment queries); SQLite falls back to JSON
# so the test suite (which uses an in-memory SQLite) can build the schema.
_JSONB_PG = JSONB().with_variant(JSON(), "sqlite")


class ResearchAgentSpecRow(Model, table=True):
    """Persisted spec for a user-defined deep research agent."""

    __tablename__ = "research_agent_specs"

    slug: str = Field(index=True, unique=True, description="URL-safe identifier")
    name: str = Field(index=True)
    description: str = Field(default="", description="Shown in picker UI")
    instructions: str = Field(default="", description="System prompt / orchestrator instructions")

    model_name: str | None = Field(default=None, description="e.g. openai:gpt-5.2")
    tool_allowlist: list[str] = Field(
        default_factory=list,
        sa_column=Column(_JSONB_PG, nullable=False, server_default="[]"),
        description="Tool names the orchestrator can call directly",
    )
    connector_bindings: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(_JSONB_PG, nullable=False, server_default="{}"),
        description="Per-connector config (e.g. {'web': {'searx_k': 10}})",
    )
    subagents: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(_JSONB_PG, nullable=False, server_default="[]"),
        description="List of the sub-agent config dicts",
    )

    owner_id: str | None = Field(default=None, index=True, description="None = system-owned default")
    is_system: bool = Field(default=False, description="System-seeded defaults (non-deletable)")
