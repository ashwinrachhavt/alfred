from __future__ import annotations

from datetime import UTC, datetime, timedelta


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""

    return datetime.now(UTC)


def utcnow_naive() -> datetime:
    """Return the current time as a naive UTC datetime.

    Prefer `utcnow()` for new code.
    """

    return datetime.now(UTC).replace(tzinfo=None)


STAGE_TO_DELTA: dict[int, timedelta] = {
    1: timedelta(days=1),
    2: timedelta(days=7),
    3: timedelta(days=30),
}


def clamp_int(val: int, *, lo: int, hi: int) -> int:
    """Clamp `val` into the inclusive range [`lo`, `hi`]."""

    return max(lo, min(hi, int(val)))


__all__ = ["STAGE_TO_DELTA", "clamp_int", "utcnow", "utcnow_naive"]
