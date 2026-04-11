"""Daily briefing generation task.

Aggregates overnight insights for the Today page:
- Recent captures (24h)
- Link suggestions from batch_link (not auto-created, user accepts)
- Due spaced repetition reviews
- Knowledge gaps (stub cards)
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from celery import shared_task
from sqlmodel import select

from alfred.core.database import SessionLocal
from alfred.models.doc_storage import DocumentRow
from alfred.models.zettel import ZettelCard, ZettelLink, ZettelReview
from alfred.schemas.today import (
    TodayBriefingResponse,
    TodayBriefingStats,
    TodayCalendarDay,
    TodayCalendarResponse,
    TodayCaptureItem,
    TodayConnectionItem,
    TodayGapItem,
    TodayReviewItem,
    TodayStoredCardItem,
)

logger = logging.getLogger(__name__)


MAX_DAY_ITEMS = 24


def _resolve_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown timezone %s, falling back to UTC", tz_name)
        return ZoneInfo("UTC")


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _ensure_aware(value).isoformat()


def _local_date(value: datetime | None, timezone: ZoneInfo) -> date | None:
    if value is None:
        return None
    return _ensure_aware(value).astimezone(timezone).date()


def _day_window(target_date: date, timezone: ZoneInfo) -> tuple[datetime, datetime]:
    local_start = datetime.combine(target_date, time.min, tzinfo=timezone)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def _date_range(start_date: date, end_date: date) -> list[date]:
    total_days = (end_date - start_date).days
    return [start_date + timedelta(days=index) for index in range(total_days + 1)]


def build_daily_briefing(
    target_date: date | None = None,
    tz_name: str = "UTC",
) -> TodayBriefingResponse:
    """Aggregate insights for a specific local day."""
    session = SessionLocal()
    try:
        timezone = _resolve_timezone(tz_name)
        now = datetime.now(UTC)
        local_today = now.astimezone(timezone).date()
        day = target_date or local_today
        day_start_utc, day_end_utc = _day_window(day, timezone)

        recent_docs = list(
            session.exec(
                select(DocumentRow)
                .where(DocumentRow.created_at >= day_start_utc)
                .where(DocumentRow.created_at < day_end_utc)
                .order_by(DocumentRow.created_at.desc())
                .limit(MAX_DAY_ITEMS)
            )
        )
        captures = [
            TodayCaptureItem(
                id=str(doc.id),
                title=doc.title or "Untitled",
                source_url=doc.source_url,
                pipeline_status=doc.pipeline_status,
                content_type=doc.content_type,
                created_at=_to_iso(doc.created_at),
            )
            for doc in recent_docs
        ]

        stored_card_rows = list(
            session.exec(
                select(ZettelCard)
                .where(ZettelCard.created_at >= day_start_utc)
                .where(ZettelCard.created_at < day_end_utc)
                .where(ZettelCard.status != "archived")
                .where(ZettelCard.status != "stub")
                .order_by(ZettelCard.created_at.desc())
                .limit(MAX_DAY_ITEMS)
            )
        )
        stored_cards = [
            TodayStoredCardItem(
                card_id=card.id or 0,
                title=card.title,
                topic=card.topic,
                status=card.status,
                tags=card.tags or [],
                created_at=_to_iso(card.created_at),
            )
            for card in stored_card_rows
            if card.id is not None
        ]

        stub_card_rows = list(
            session.exec(
                select(ZettelCard)
                .where(ZettelCard.created_at >= day_start_utc)
                .where(ZettelCard.created_at < day_end_utc)
                .where(ZettelCard.status == "stub")
                .order_by(ZettelCard.created_at.desc())
                .limit(MAX_DAY_ITEMS)
            )
        )
        gaps = [
            TodayGapItem(
                card_id=card.id or 0,
                title=card.title,
                created_at=_to_iso(card.created_at),
            )
            for card in stub_card_rows
            if card.id is not None
        ]

        due_review_rows = list(
            session.exec(
                select(ZettelReview)
                .where(ZettelReview.due_at >= day_start_utc)
                .where(ZettelReview.due_at < day_end_utc)
                .order_by(ZettelReview.due_at.asc())
                .limit(MAX_DAY_ITEMS)
            )
        )
        due_card_ids = [review.card_id for review in due_review_rows]
        due_cards: dict[int, ZettelCard] = {}
        if due_card_ids:
            cards = list(session.exec(select(ZettelCard).where(ZettelCard.id.in_(due_card_ids))))
            due_cards = {card.id or 0: card for card in cards if card.id is not None}

        reviews = [
            TodayReviewItem(
                review_id=review.id or 0,
                card_id=review.card_id,
                card_title=due_cards.get(review.card_id, ZettelCard(title="Unknown")).title,
                stage=review.stage,
                due_at=_to_iso(review.due_at),
                completed_at=_to_iso(review.completed_at),
                status="completed" if review.completed_at else "pending",
            )
            for review in due_review_rows
            if review.id is not None
        ]

        recent_links = list(
            session.exec(
                select(ZettelLink)
                .where(ZettelLink.created_at >= day_start_utc)
                .where(ZettelLink.created_at < day_end_utc)
                .order_by(ZettelLink.created_at.desc())
                .limit(MAX_DAY_ITEMS)
            )
        )
        link_card_ids: set[int] = set()
        for link in recent_links:
            link_card_ids.add(link.from_card_id)
            link_card_ids.add(link.to_card_id)

        link_cards: dict[int, ZettelCard] = {}
        if link_card_ids:
            cards = list(session.exec(select(ZettelCard).where(ZettelCard.id.in_(list(link_card_ids)))))
            link_cards = {card.id or 0: card for card in cards if card.id is not None}

        connections = [
            TodayConnectionItem(
                link_id=link.id or 0,
                from_card_id=link.from_card_id,
                from_title=link_cards.get(link.from_card_id, ZettelCard(title="Unknown")).title,
                to_card_id=link.to_card_id,
                to_title=link_cards.get(link.to_card_id, ZettelCard(title="Unknown")).title,
                type=link.type,
                created_at=_to_iso(link.created_at),
            )
            for link in recent_links
            if link.id is not None
        ]

        total_cards = len(list(session.exec(select(ZettelCard.id).where(ZettelCard.status != "archived"))))
        total_links = len(list(session.exec(select(ZettelLink.id))))
        completed_reviews = sum(1 for review in reviews if review.completed_at)

        briefing = TodayBriefingResponse(
            date=day.isoformat(),
            timezone=timezone.key,
            generated_at=now.isoformat(),
            captures=captures,
            stored_cards=stored_cards,
            connections=connections,
            reviews=reviews,
            gaps=gaps,
            stats=TodayBriefingStats(
                total_captures=len(captures),
                total_cards_created=len(stored_cards),
                total_connections=len(connections),
                total_reviews_due=len(reviews),
                total_reviews_completed=completed_reviews,
                total_gaps=len(gaps),
                total_events=len(captures) + len(stored_cards) + len(connections) + len(reviews) + len(gaps),
                total_cards=total_cards,
                total_links=total_links,
            ),
        )

        logger.info(
            "Daily briefing for %s (%s): %d captures, %d cards, %d connections, %d reviews, %d gaps",
            briefing.date,
            briefing.timezone,
            len(captures),
            len(stored_cards),
            len(connections),
            len(reviews),
            len(gaps),
        )
        return briefing
    finally:
        session.close()


def build_today_calendar(
    start_date: date | None = None,
    end_date: date | None = None,
    days: int = 120,
    tz_name: str = "UTC",
) -> TodayCalendarResponse:
    """Build day-level activity counts for the calendar view."""
    session = SessionLocal()
    try:
        timezone = _resolve_timezone(tz_name)
        local_today = datetime.now(UTC).astimezone(timezone).date()
        final_end_date = end_date or local_today
        final_start_date = start_date or (final_end_date - timedelta(days=days - 1))
        if final_start_date > final_end_date:
            final_start_date, final_end_date = final_end_date, final_start_date

        range_start_utc, _ = _day_window(final_start_date, timezone)
        _, range_end_utc = _day_window(final_end_date, timezone)

        day_map = {
            current_day: TodayCalendarDay(date=current_day.isoformat())
            for current_day in _date_range(final_start_date, final_end_date)
        }

        recent_docs = list(
            session.exec(
                select(DocumentRow.created_at)
                .where(DocumentRow.created_at >= range_start_utc)
                .where(DocumentRow.created_at < range_end_utc)
            )
        )
        for created_at in recent_docs:
            day = _local_date(created_at, timezone)
            if day is None or day not in day_map:
                continue
            day_map[day].captures += 1
            day_map[day].total_events += 1

        recent_cards = list(
            session.exec(
                select(ZettelCard.created_at, ZettelCard.status)
                .where(ZettelCard.created_at >= range_start_utc)
                .where(ZettelCard.created_at < range_end_utc)
                .where(ZettelCard.status != "archived")
            )
        )
        for created_at, status in recent_cards:
            day = _local_date(created_at, timezone)
            if day is None or day not in day_map:
                continue
            if status == "stub":
                day_map[day].gaps += 1
            else:
                day_map[day].stored_cards += 1
            day_map[day].total_events += 1

        recent_links = list(
            session.exec(
                select(ZettelLink.created_at)
                .where(ZettelLink.created_at >= range_start_utc)
                .where(ZettelLink.created_at < range_end_utc)
            )
        )
        for created_at in recent_links:
            day = _local_date(created_at, timezone)
            if day is None or day not in day_map:
                continue
            day_map[day].connections += 1
            day_map[day].total_events += 1

        review_rows = list(
            session.exec(
                select(ZettelReview.due_at, ZettelReview.completed_at)
                .where(ZettelReview.due_at >= range_start_utc)
                .where(ZettelReview.due_at < range_end_utc)
            )
        )
        for due_at, completed_at in review_rows:
            day = _local_date(due_at, timezone)
            if day is None or day not in day_map:
                continue
            day_map[day].reviews_due += 1
            day_map[day].total_events += 1
            if completed_at is not None:
                day_map[day].reviews_completed += 1

        return TodayCalendarResponse(
            start_date=final_start_date.isoformat(),
            end_date=final_end_date.isoformat(),
            timezone=timezone.key,
            days=[day_map[current_day] for current_day in _date_range(final_start_date, final_end_date)],
        )
    finally:
        session.close()


@shared_task(name="alfred.tasks.daily_briefing.generate")
def generate_daily_briefing() -> dict:
    """Celery wrapper for the default 'today' briefing."""
    return build_daily_briefing().model_dump(mode="json")
