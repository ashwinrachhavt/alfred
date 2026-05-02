"""Shared interface for any event consumer (projector)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from alfred.streaming.events import AnyRunEvent


@runtime_checkable
class EventConsumer(Protocol):
    """A projector that observes emitted events and produces derivative state.

    Consumers are synchronous, pure enough to run against a replayed event stream.
    IO a consumer wants to do (e.g., DB writes) should be triggered by
    ``on_run_finished`` so it runs once per run, not per event.
    """

    def on_event(self, event: AnyRunEvent) -> None: ...
    def on_run_finished(self, terminal: AnyRunEvent) -> None: ...
