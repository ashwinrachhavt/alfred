"""Streaming substrate: typed events, recorder, projectors, replay.

Spec: docs/superpowers/specs/2026-05-01-streaming-revamp-design.md
"""

from alfred.streaming.consumers import EventConsumer
from alfred.streaming.events import (
    AnyRunEvent,
    ApprovalRequired,
    ApprovalResolved,
    MessageDelta,
    MessageFinished,
    MessageStarted,
    ProgressUpdate,
    RunCancelled,
    RunErrored,
    RunFinished,
    RunStarted,
    RunType,
    StateDelta,
    StateOp,
    StateSnapshot,
    ThinkingDelta,
    ThinkingFinished,
    ToolArgsDelta,
    ToolArgsFinished,
    ToolResult,
    ToolResultStatus,
    ToolStarted,
)
from alfred.streaming.projectors.message_row import MessageProjector
from alfred.streaming.projectors.snapshot import SnapshotProjector
from alfred.streaming.projectors.wire_agui import AGUIProjector
from alfred.streaming.recorder import RunRecorder
from alfred.streaming.replay import ReplayEngine

__all__ = [
    "EventConsumer",
    "AnyRunEvent", "RunType", "StateOp", "ToolResultStatus",
    "RunStarted", "RunFinished", "RunErrored", "RunCancelled",
    "MessageStarted", "MessageDelta", "MessageFinished",
    "ThinkingDelta", "ThinkingFinished",
    "ToolStarted", "ToolArgsDelta", "ToolArgsFinished", "ToolResult",
    "StateDelta", "StateSnapshot",
    "ProgressUpdate", "ApprovalRequired", "ApprovalResolved",
    "RunRecorder", "ReplayEngine",
    "AGUIProjector", "MessageProjector", "SnapshotProjector",
]
