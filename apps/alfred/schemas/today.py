from __future__ import annotations

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
