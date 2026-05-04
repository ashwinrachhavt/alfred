"""Pydantic request/response schemas for deep research agents."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SubAgentSpec(BaseModel):
    """Matches the dict shape deepagents expects in `subagents=[...]`."""

    name: str
    description: str = Field(..., description="Shown to orchestrator for delegation decisions")
    system_prompt: str
    tools: list[str] = Field(default_factory=list, description="Tool names from registry")
    model: str | None = Field(default=None, description="Optional per-subagent model override")


class ResearchAgentSpecCreate(BaseModel):
    slug: str
    name: str
    description: str = ""
    instructions: str = ""
    model_name: str | None = None
    tool_allowlist: list[str] = Field(default_factory=list)
    connector_bindings: dict[str, Any] = Field(default_factory=dict)
    subagents: list[SubAgentSpec] = Field(default_factory=list)


class ResearchAgentSpecUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    instructions: str | None = None
    model_name: str | None = None
    tool_allowlist: list[str] | None = None
    connector_bindings: dict[str, Any] | None = None
    subagents: list[SubAgentSpec] | None = None


class ResearchAgentSpecOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    instructions: str
    model_name: str | None
    tool_allowlist: list[str]
    connector_bindings: dict[str, Any]
    subagents: list[SubAgentSpec]
    is_system: bool
    owner_id: str | None = None

    model_config = {"from_attributes": True}


class ToolCatalogEntry(BaseModel):
    """Describes a tool available for inclusion in a spec."""

    name: str
    description: str
    requires_connector: str | None = None
    category: str = "general"


class RunRequest(BaseModel):
    """Request body for POST /api/research/run."""

    topic: str = Field(..., min_length=1)
    agent_spec_id: int | None = Field(default=None, description="Use persisted spec by id")
    inline_spec: ResearchAgentSpecCreate | None = Field(
        default=None, description="Ad-hoc spec for one-off runs; ignored if agent_spec_id is set"
    )
    thread_id: int | None = None
