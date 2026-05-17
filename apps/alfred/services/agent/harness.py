"""Shared agent harness primitives.

This module is deliberately framework-light. It gives every Alfred agent the same
runtime vocabulary: agent specs, run contexts, policy decisions, event traces,
and compact tool-result envelopes. LangChain/LangGraph integrations can use
these types, but direct OpenAI loops can use them too.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

AgentRiskProfile = Literal["read_only", "standard", "writer", "networked", "admin"]
ToolRiskTier = Literal["read", "soft_write", "hard_write", "network", "destructive"]
PolicyAction = Literal["allow", "deny", "ask"]


class AgentEventType(str, Enum):
    """Canonical event names emitted by Alfred agent runs."""

    AGENT_STARTED = "agent.started"
    MODEL_STARTED = "model.started"
    MODEL_COMPLETED = "model.completed"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_BLOCKED = "tool.blocked"
    ARTIFACT_CREATED = "artifact.created"
    AGENT_COMPLETED = "agent.completed"
    AGENT_ERROR = "agent.error"


@dataclass(frozen=True)
class AgentSpec:
    """Definition of one Alfred agent surface.

    Existing specialist `AgentType` definitions can be projected into this type;
    new agents should register directly as `AgentSpec` so the runtime can apply
    consistent tool policy, tracing, and middleware.
    """

    name: str
    description: str
    system_prompt: str
    tool_names: tuple[str, ...] = ()
    max_iterations: int = 10
    risk_profile: AgentRiskProfile = "standard"
    prompt_version: str = "v1"
    supports_streaming: bool = False
    artifact_policy: Literal["off", "auto", "always"] = "auto"


@dataclass(frozen=True)
class AgentRunContext:
    """Per-run metadata passed through the harness."""

    agent_name: str
    run_id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")
    thread_id: str | None = None
    user_id: str | int | None = None
    parent_run_id: str | None = None
    model: str | None = None
    prompt_version: str | None = None


@dataclass(frozen=True)
class AgentEvent:
    """Replay-grade event captured at the model/tool boundary."""

    type: AgentEventType
    run_id: str
    timestamp: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRunTrace:
    """In-memory trace for one agent run.

    Persistence can be layered later; this already gives callers a stable event
    shape and deterministic hashes for replay assertions.
    """

    context: AgentRunContext
    events: list[AgentEvent] = field(default_factory=list)

    def emit(self, event_type: AgentEventType, **data: Any) -> AgentEvent:
        event = AgentEvent(
            type=event_type,
            run_id=self.context.run_id,
            timestamp=datetime.now(UTC).isoformat(),
            data=data,
        )
        self.events.append(event)
        return event


@dataclass(frozen=True)
class ToolPolicyDecision:
    action: PolicyAction
    tier: ToolRiskTier
    reason: str


@dataclass(frozen=True)
class ToolResultEnvelope:
    """Compact, typed tool result returned to model context."""

    status: Literal["ok", "error", "blocked"]
    summary: str
    structured: dict[str, Any] = field(default_factory=dict)
    artifact_refs: tuple[str, ...] = ()
    preview: tuple[str, ...] = ()
    raw_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "structured": self.structured,
            "artifact_refs": list(self.artifact_refs),
            "preview": list(self.preview),
            "raw_hash": self.raw_hash,
        }


_READ_TOOLS = frozenset(
    {
        "search_kb",
        "get_zettel",
        "list_recent_cards",
        "search_documents",
        "get_document",
        "find_similar",
        "get_card_links",
        "get_due_reviews",
        "assess_knowledge",
        "generate_quiz",
        "feynman_check",
        "feynman_explain",
        "progressive_summary",
        "compare_perspectives",
        "search_kb_for_research",
        "query_wikipedia",
        "query_arxiv",
        "query_semantic_scholar",
        "query_rss",
        "query_github",
        "query_linear",
        "list_connectors",
        "import_status",
        "summarize",
        "extract_concepts",
        "classify_document",
    }
)

_SOFT_WRITE_TOOLS = frozenset(
    {
        "draft_zettel",
        "create_zettel_from_synthesis",
        "decompose_to_zettels",
    }
)

_HARD_WRITE_TOOLS = frozenset(
    {
        "create_zettel",
        "update_zettel",
        "create_link",
        "batch_link",
        "submit_review",
        "run_import",
        "import_notes_from_filesystem",
    }
)

_NETWORK_TOOLS = frozenset(
    {
        "web_search_searxng",
        "search_web",
        "query_web",
        "firecrawl_search",
        "firecrawl_scrape",
        "scrape_url",
        "search_papers",
        "deep_research",
        "query_notion",
        "query_readwise",
    }
)

_DESTRUCTIVE_PREFIXES = ("delete_", "destroy_", "purge_", "force_")


def classify_tool_risk(tool_name: str) -> ToolRiskTier:
    """Classify a tool into Alfred's deterministic risk tiers."""

    if tool_name.startswith(_DESTRUCTIVE_PREFIXES):
        return "destructive"
    if tool_name in _NETWORK_TOOLS:
        return "network"
    if tool_name in _HARD_WRITE_TOOLS:
        return "hard_write"
    if tool_name in _SOFT_WRITE_TOOLS:
        return "soft_write"
    if tool_name in _READ_TOOLS:
        return "read"
    if any(token in tool_name for token in ("create", "update", "write", "import", "link")):
        return "hard_write"
    if any(token in tool_name for token in ("web", "scrape", "search_papers", "query_")):
        return "network"
    return "read"


@dataclass(frozen=True)
class AgentPolicy:
    """Deterministic guardrail in front of tool execution."""

    allow_writes: bool = True
    allow_network: bool = True
    allow_destructive: bool = False
    require_approval_for_hard_writes: bool = False

    def decide(self, tool_name: str, _args: dict[str, Any]) -> ToolPolicyDecision:
        tier = classify_tool_risk(tool_name)
        if tier == "destructive" and not self.allow_destructive:
            return ToolPolicyDecision("deny", tier, "Destructive tools are disabled by default.")
        if tier == "network" and not self.allow_network:
            return ToolPolicyDecision("deny", tier, "Network tools are disabled for this run.")
        if tier in {"soft_write", "hard_write"} and not self.allow_writes:
            return ToolPolicyDecision("deny", tier, "Write tools are disabled for this run.")
        if tier == "hard_write" and self.require_approval_for_hard_writes:
            return ToolPolicyDecision("ask", tier, "Hard-write tools require approval.")
        return ToolPolicyDecision("allow", tier, "Allowed by agent policy.")


DEFAULT_AGENT_POLICY = AgentPolicy()


def stable_hash(value: Any) -> str:
    """Return a deterministic SHA-256 hash for replay-grade traces."""

    try:
        payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    except TypeError:
        payload = str(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_tool_result(result: dict[str, Any] | Any, *, max_preview_chars: int = 1200) -> ToolResultEnvelope:
    """Convert arbitrary tool output into a compact context envelope.

    The full raw value is represented by a hash. Artifact persistence can later
    store oversized payloads keyed by the same hash without changing the model
    contract.
    """

    raw_hash = stable_hash(result)
    if isinstance(result, dict):
        if "error" in result and result.get("error"):
            return ToolResultEnvelope(
                status="error",
                summary=str(result.get("error"))[:max_preview_chars],
                structured={"error": result.get("error")},
                raw_hash=raw_hash,
            )

        action = result.get("action")
        title = result.get("title") or result.get("name") or result.get("zettel_title")
        count = result.get("count") or result.get("total") or result.get("total_count")
        summary_parts: list[str] = []
        if action:
            summary_parts.append(str(action))
        if title:
            summary_parts.append(str(title))
        if count is not None:
            summary_parts.append(f"count={count}")
        summary = "; ".join(summary_parts) or "Tool completed."

        preview: list[str] = []
        for key in ("summary", "result", "message", "answer"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                preview.append(value.strip()[:max_preview_chars])
                break

        return ToolResultEnvelope(
            status="ok",
            summary=summary[:max_preview_chars],
            structured=result,
            preview=tuple(preview),
            raw_hash=raw_hash,
        )

    text = str(result)
    return ToolResultEnvelope(
        status="ok",
        summary=text[:max_preview_chars] if text else "Tool completed.",
        structured={"result": text},
        preview=(text[:max_preview_chars],) if text else (),
        raw_hash=raw_hash,
    )


def wrap_untrusted_data(label: str, content: str) -> str:
    """Mark retrieved/user-provided content as data, not instructions."""

    return (
        f"BEGIN UNTRUSTED DATA: {label}\n"
        f"{content}\n"
        f"END UNTRUSTED DATA: {label}"
    )
