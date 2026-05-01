from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class TodayCaptureItem(BaseModel):
    id: str
    title: str
    source_url: str | None = None
    pipeline_status: str
    content_type: str | None = None
    created_at: str | None = None


class TodayStoredCardItem(BaseModel):
    card_id: int
    title: str
    topic: str | None = None
    status: str
    tags: list[str] = Field(default_factory=list)
    created_at: str | None = None


class TodayConnectionItem(BaseModel):
    link_id: int
    from_card_id: int
    from_title: str
    to_card_id: int
    to_title: str
    type: str
    created_at: str | None = None


class TodayReviewItem(BaseModel):
    review_id: int
    card_id: int
    card_title: str
    stage: int
    due_at: str | None = None
    completed_at: str | None = None
    status: str


class TodayGapItem(BaseModel):
    card_id: int
    title: str
    created_at: str | None = None


class TodayBriefingStats(BaseModel):
    total_captures: int = 0
    total_cards_created: int = 0
    total_connections: int = 0
    total_reviews_due: int = 0
    total_reviews_completed: int = 0
    total_gaps: int = 0
    total_events: int = 0
    total_cards: int = 0
    total_links: int = 0


class TodayBriefingResponse(BaseModel):
    date: str
    timezone: str
    generated_at: str
    captures: list[TodayCaptureItem] = Field(default_factory=list)
    stored_cards: list[TodayStoredCardItem] = Field(default_factory=list)
    connections: list[TodayConnectionItem] = Field(default_factory=list)
    reviews: list[TodayReviewItem] = Field(default_factory=list)
    gaps: list[TodayGapItem] = Field(default_factory=list)
    stats: TodayBriefingStats


class TodayCalendarDay(BaseModel):
    date: str
    captures: int = 0
    stored_cards: int = 0
    connections: int = 0
    reviews_due: int = 0
    reviews_completed: int = 0
    gaps: int = 0
    total_events: int = 0


class TodayCalendarResponse(BaseModel):
    start_date: str
    end_date: str
    timezone: str
    days: list[TodayCalendarDay] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# DailyEntry CRUD schemas (T3)
# ---------------------------------------------------------------------------


class DailyEntryCreate(BaseModel):
    """Create payload for a daily entry. ``kind`` is validated in the route
    layer (rejects ``artifact_ref``) so that Pydantic stays permissive."""

    entry_date: date
    kind: str
    title: str = Field(min_length=1, max_length=500)
    body_md: str = ""
    status: str = "open"
    priority: int = 0
    tags: list[str] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)
    user_id: str | None = None


class DailyEntryUpdate(BaseModel):
    """Partial patch; every field optional."""

    kind: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    body_md: str | None = None
    status: str | None = None
    priority: int | None = None
    tags: list[str] | None = None
    meta: dict | None = None
    entry_date: date | None = None


class DailyEntryItem(BaseModel):
    """Single entry as returned by ``GET /api/today/entries``.

    ``id`` is ``int`` for real rows and ``str`` (e.g. ``"zettel:123"``) for
    synthetic artifact-ref rows derived from zettels/captures/reviews.
    """

    id: int | str
    kind: str
    entry_date: str
    title: str
    body_md: str = ""
    status: str | None = None
    priority: int = 0
    tags: list[str] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None
    is_synthetic: bool = False


class DailyEntriesResponse(BaseModel):
    entries: list[DailyEntryItem]
    next_cursor: str | None = None
    total: int = 0


# ---------------------------------------------------------------------------
# Daily reflection + manual pipeline trigger (T12)
# ---------------------------------------------------------------------------


class DailyReflectionResponse(BaseModel):
    """End-of-day digest returned by ``GET /api/today/reflections/{date}``."""

    id: int
    entry_date: str  # ISO date
    digest_md: str
    stats: dict
    pipeline_run_id: str
    stages_ran: list[str]
    generated_at: str
    user_id: str | None = None

    @classmethod
    def from_row(cls, row: Any) -> DailyReflectionResponse:
        """Build the response from a :class:`DailyReflectionRow`.

        Typed as ``Any`` to avoid a schema->model import cycle; the
        attribute access is structural and safe because the row shape is
        stable (see ``alfred.models.today.DailyReflectionRow``).
        """
        generated_at = getattr(row, "generated_at", None)
        return cls(
            id=row.id,
            entry_date=row.entry_date.isoformat(),
            digest_md=row.digest_md or "",
            stats=dict(row.stats or {}),
            pipeline_run_id=row.pipeline_run_id or "",
            stages_ran=list(row.stages_ran or []),
            generated_at=generated_at.isoformat() if generated_at else "",
            user_id=getattr(row, "user_id", None),
        )


class PipelineRunRequest(BaseModel):
    """Payload for ``POST /api/today/pipeline/run`` manual trigger."""

    entry_date: date
    tz: str = "UTC"
    user_id: str | None = None
    # ``False`` — synchronous execution for dev / small deployments.
    # ``True``  — dispatch to the Celery worker via ``.delay(...)``.
    enqueue: bool = False


class PipelineRunResponse(BaseModel):
    dispatched: bool
    task_id: str | None = None
    result: dict | None = None
