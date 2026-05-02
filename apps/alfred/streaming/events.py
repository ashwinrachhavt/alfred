"""Typed domain events for the streaming substrate.

Every AI invocation in Alfred emits a stream of these events.
See docs/superpowers/specs/2026-05-01-streaming-revamp-design.md section 4.

Invariants:
  - Monotonic ``seq`` per ``run_id`` (recorder-assigned).
  - Domain-layer IDs are UUIDv4; wire-layer may synthesize derivative string ids.
  - Append-only; no event is ever mutated.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RunType = Literal[
    "chat_turn",
    "llm_call",
    "tool_call",
    "subagent",
    "zettel_create",
    "writing_compose",
    "reading_summarize",
]


class _EventBase(BaseModel):
    """Shared fields across every event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: UUID
    seq: int = Field(ge=0)
    emitted_at: datetime


class RunStarted(_EventBase):
    event_type: Literal["run.started"] = "run.started"
    parent_run_id: UUID | None = None
    run_type: RunType
    thread_id: int | None = None
    user_id: str | None = None
    input_summary: str | None = None
    model_id: str | None = None
    active_lens: str | None = None


class RunFinished(_EventBase):
    event_type: Literal["run.finished"] = "run.finished"
    duration_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None


class RunErrored(_EventBase):
    event_type: Literal["run.errored"] = "run.errored"
    error_type: str
    error_message: str


class RunCancelled(_EventBase):
    event_type: Literal["run.cancelled"] = "run.cancelled"
    reason: str | None = None


class MessageStarted(_EventBase):
    event_type: Literal["message.started"] = "message.started"
    message_id: UUID
    role: Literal["assistant"] = "assistant"


class MessageDelta(_EventBase):
    event_type: Literal["message.delta"] = "message.delta"
    message_id: UUID
    delta_text: str


class MessageFinished(_EventBase):
    event_type: Literal["message.finished"] = "message.finished"
    message_id: UUID
    final_text: str
    token_count: int | None = None


class ThinkingDelta(_EventBase):
    event_type: Literal["thinking.delta"] = "thinking.delta"
    message_id: UUID
    delta_text: str


class ThinkingFinished(_EventBase):
    event_type: Literal["thinking.finished"] = "thinking.finished"
    message_id: UUID
    full_text: str


class ToolStarted(_EventBase):
    event_type: Literal["tool.started"] = "tool.started"
    tool_call_id: str
    tool_name: str
    parent_message_id: UUID | None = None
    args_preview: dict[str, Any] = Field(default_factory=dict)


class ToolArgsDelta(_EventBase):
    event_type: Literal["tool.args.delta"] = "tool.args.delta"
    tool_call_id: str
    delta_json: str


class ToolArgsFinished(_EventBase):
    event_type: Literal["tool.args.finished"] = "tool.args.finished"
    tool_call_id: str
    full_args: dict[str, Any]


ToolResultStatus = Literal["ok", "error", "timeout"]


class ToolResult(_EventBase):
    event_type: Literal["tool.result"] = "tool.result"
    tool_call_id: str
    result_json: dict[str, Any]
    duration_ms: int
    status: ToolResultStatus


StateOp = Literal["set", "append", "merge", "remove"]


class StateDelta(_EventBase):
    event_type: Literal["state.delta"] = "state.delta"
    key: str
    op: StateOp
    value: Any


class StateSnapshot(_EventBase):
    event_type: Literal["state.snapshot"] = "state.snapshot"
    state: dict[str, Any]


class ProgressUpdate(_EventBase):
    event_type: Literal["progress.update"] = "progress.update"
    stage: str
    message: str | None = None
    pct_complete: float | None = None


class ApprovalRequired(_EventBase):
    event_type: Literal["approval.required"] = "approval.required"
    approval_id: UUID
    action: str
    payload: dict[str, Any]
    reason: str | None = None


class ApprovalResolved(_EventBase):
    event_type: Literal["approval.resolved"] = "approval.resolved"
    approval_id: UUID
    decision: Literal["approved", "rejected"]
    resolved_by: str | None = None


AnyRunEvent = Annotated[
    RunStarted | RunFinished | RunErrored | RunCancelled | MessageStarted | MessageDelta | MessageFinished | ThinkingDelta | ThinkingFinished | ToolStarted | ToolArgsDelta | ToolArgsFinished | ToolResult | StateDelta | StateSnapshot | ProgressUpdate | ApprovalRequired | ApprovalResolved,
    Field(discriminator="event_type"),
]


__all__ = [
    "RunType", "ToolResultStatus", "StateOp", "AnyRunEvent",
    "RunStarted", "RunFinished", "RunErrored", "RunCancelled",
    "MessageStarted", "MessageDelta", "MessageFinished",
    "ThinkingDelta", "ThinkingFinished",
    "ToolStarted", "ToolArgsDelta", "ToolArgsFinished", "ToolResult",
    "StateDelta", "StateSnapshot",
    "ProgressUpdate", "ApprovalRequired", "ApprovalResolved",
]
