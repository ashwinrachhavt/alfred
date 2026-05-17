"""Lightweight task-system metric counters.

This module intentionally stays dependency-free. Production telemetry can scrape or
replace these counters later without changing task-system call sites.
"""

from __future__ import annotations

from collections import Counter
from threading import Lock

_COUNTERS: Counter[str] = Counter()
_LOCK = Lock()


def increment_task_metric(name: str, value: int = 1) -> None:
    with _LOCK:
        _COUNTERS[name] += value


def snapshot_task_metrics() -> dict[str, int]:
    with _LOCK:
        return dict(_COUNTERS)


__all__ = ["increment_task_metric", "snapshot_task_metrics"]
