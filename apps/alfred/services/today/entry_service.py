"""Today/Daily entry service.

Handles CRUD for ``DailyEntryRow`` plus read-time synthesis of
``artifact_ref`` items drawn from zettels, captures (documents), and
reviews. Artifacts are never written - they are always derived from the
source tables so there is no divergence.

Convention: dataclass-based service, takes a ``Session`` in its
constructor and exposes small, composable methods.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func
from sqlmodel import Session, select

from alfred.models.doc_storage import DocumentRow
from alfred.models.today import DailyEntryRow
from alfred.models.zettel import ZettelCard, ZettelReview

VALID_KINDS: set[str] = {"todo", "note", "learning"}
VALID_STATUSES: set[str] = {"open", "doing", "done", "skipped"}
ARTIFACT_KIND = "artifact_ref"

# Upper bound on artifact-source rows we synthesize per list call. Keeps
# pathological ranges from materialising huge result sets. Real entries
# remain cursor-paginated.
_MAX_ARTIFACT_ROWS_PER_SOURCE = 500


# ---------------------------------------------------------------------------
# Tz helpers (mirrors daily_briefing.py - reused pattern, local copy to keep
# the service free of celery-task imports)
# ---------------------------------------------------------------------------


def _resolve_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _local_date(value: datetime | None, tz: ZoneInfo) -> date | None:
    if value is None:
        return None
    return _ensure_aware(value).astimezone(tz).date()


def _day_window(target: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    local_start = datetime.combine(target, time.min, tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def _range_window(start: date, end: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """UTC half-open window spanning [start, end] inclusive in tz-local dates."""
    start_utc, _ = _day_window(start, tz)
    _, end_utc = _day_window(end, tz)
    return start_utc, end_utc


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _ensure_aware(value).isoformat()


# ---------------------------------------------------------------------------
# Cursor (opaque base64 of {date, id})
# ---------------------------------------------------------------------------


def _encode_cursor(*, entry_date: date, row_id: int) -> str:
    payload = {"d": entry_date.isoformat(), "i": row_id}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[date, int]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
        payload = json.loads(raw.decode("utf-8"))
        return date.fromisoformat(payload["d"]), int(payload["i"])
    except Exception as error:
        raise ValueError(f"invalid cursor: {cursor!r}") from error


@dataclass
class EntriesPage:
    """Paged response for ``list_entries``."""

    entries: list[dict[str, Any]] = field(default_factory=list)
    next_cursor: str | None = None
    total: int = 0


@dataclass
class EntryService:
    """Domain service for daily entries + artifact synthesis."""

    session: Session

    # -----------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------
    def create_entry(
        self,
        *,
        entry_date: date,
        kind: str,
        title: str,
        body_md: str = "",
        status: str = "open",
        priority: int = 0,
        tags: list[str] | None = None,
        meta: dict | None = None,
        user_id: str | None = None,
    ) -> DailyEntryRow:
        if kind not in VALID_KINDS:
            raise ValueError(f"invalid kind {kind!r}; must be one of {sorted(VALID_KINDS)}")
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status {status!r}; must be one of {sorted(VALID_STATUSES)}")
        if not title or not title.strip():
            raise ValueError("title must not be empty")

        row = DailyEntryRow(
            user_id=user_id,
            entry_date=entry_date,
            kind=kind,
            title=title.strip(),
            body_md=body_md or "",
            status=status,
            priority=int(priority),
            tags=list(tags or []),
            meta=dict(meta or {}),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_entry(
        self,
        entry_id: int,
        *,
        user_id: str | None = None,
    ) -> DailyEntryRow | None:
        row = self.session.get(DailyEntryRow, entry_id)
        if row is None:
            return None
        if user_id is not None and row.user_id is not None and row.user_id != user_id:
            return None
        return row

    def update_entry(
        self,
        entry_id: int,
        *,
        patch: dict,
        user_id: str | None = None,
    ) -> DailyEntryRow:
        row = self.get_entry(entry_id, user_id=user_id)
        if row is None:
            raise ValueError(f"entry {entry_id} not found")

        allowed = {
            "entry_date",
            "kind",
            "title",
            "body_md",
            "status",
            "priority",
            "tags",
            "meta",
        }
        for key, value in patch.items():
            if key not in allowed:
                continue
            if key == "kind" and value not in VALID_KINDS:
                raise ValueError(f"invalid kind {value!r}")
            if key == "status" and value not in VALID_STATUSES:
                raise ValueError(f"invalid status {value!r}")
            if key == "title":
                if not value or not str(value).strip():
                    raise ValueError("title must not be empty")
                setattr(row, key, str(value).strip())
                continue
            if key == "tags":
                setattr(row, key, list(value or []))
                continue
            if key == "meta":
                setattr(row, key, dict(value or {}))
                continue
            setattr(row, key, value)

        row.updated_at = datetime.now(UTC)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def delete_entry(
        self,
        entry_id: int,
        *,
        user_id: str | None = None,
    ) -> bool:
        row = self.get_entry(entry_id, user_id=user_id)
        if row is None:
            return False
        self.session.delete(row)
        self.session.commit()
        return True

    # -----------------------------------------------------------------
    # Listing
    # -----------------------------------------------------------------
    def list_entries(
        self,
        *,
        start: date,
        end: date,
        tz_name: str = "UTC",
        kinds: list[str] | None = None,
        statuses: list[str] | None = None,
        tags: list[str] | None = None,
        q: str | None = None,
        include_artifacts: bool = True,
        user_id: str | None = None,
        limit: int = 500,
        cursor: str | None = None,
    ) -> EntriesPage:
        if end < start:
            raise ValueError("end must be >= start")
        limit = max(1, min(int(limit), 1000))

        tz = _resolve_timezone(tz_name)

        real_rows = self._fetch_real_rows(
            start=start,
            end=end,
            kinds=kinds,
            statuses=statuses,
            q=q,
            user_id=user_id,
            limit=limit,
            cursor=cursor,
        )
        if tags:
            wanted = set(tags)
            real_rows = [r for r in real_rows if wanted.issubset(set(r.tags or []))]

        has_more = len(real_rows) > limit
        page_rows = real_rows[:limit]

        want_artifacts = include_artifacts and (not kinds or ARTIFACT_KIND in kinds)
        if kinds and ARTIFACT_KIND not in kinds:
            want_artifacts = False

        artifact_items: list[dict[str, Any]] = []
        if want_artifacts:
            artifact_items = self._synthesize_artifacts(start=start, end=end, tz=tz)

        real_items = [_serialize_real(r) for r in page_rows]
        merged = real_items + artifact_items
        merged.sort(key=_sort_key, reverse=True)

        next_cursor: str | None = None
        if has_more and page_rows:
            last = page_rows[-1]
            if last.id is not None:
                next_cursor = _encode_cursor(entry_date=last.entry_date, row_id=last.id)

        total = self._count_total(
            start=start,
            end=end,
            kinds=kinds,
            statuses=statuses,
            tags=tags,
            q=q,
            user_id=user_id,
            include_artifacts=want_artifacts,
            synthetic_count=len(artifact_items),
        )

        return EntriesPage(entries=merged, next_cursor=next_cursor, total=total)

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    def _fetch_real_rows(
        self,
        *,
        start: date,
        end: date,
        kinds: list[str] | None,
        statuses: list[str] | None,
        q: str | None,
        user_id: str | None,
        limit: int,
        cursor: str | None,
    ) -> list[DailyEntryRow]:
        stmt = (
            select(DailyEntryRow)
            .where(DailyEntryRow.entry_date >= start)
            .where(DailyEntryRow.entry_date <= end)
        )
        if user_id is not None:
            stmt = stmt.where(DailyEntryRow.user_id == user_id)
        if kinds:
            real_kinds = [k for k in kinds if k != ARTIFACT_KIND]
            if real_kinds:
                stmt = stmt.where(DailyEntryRow.kind.in_(real_kinds))
            else:
                # Only artifact_ref was requested: no real rows satisfy this.
                return []
        if statuses:
            stmt = stmt.where(DailyEntryRow.status.in_(list(statuses)))
        if q:
            like = f"%{q.strip().lower()}%"
            stmt = stmt.where(func.lower(DailyEntryRow.title).like(like))

        if cursor:
            cur_date, cur_id = _decode_cursor(cursor)
            stmt = stmt.where(
                (DailyEntryRow.entry_date < cur_date)
                | ((DailyEntryRow.entry_date == cur_date) & (DailyEntryRow.id < cur_id))
            )

        stmt = stmt.order_by(DailyEntryRow.entry_date.desc(), DailyEntryRow.id.desc()).limit(
            limit + 1
        )
        return list(self.session.exec(stmt))

    def _count_total(
        self,
        *,
        start: date,
        end: date,
        kinds: list[str] | None,
        statuses: list[str] | None,
        tags: list[str] | None,
        q: str | None,
        user_id: str | None,
        include_artifacts: bool,
        synthetic_count: int,
    ) -> int:
        stmt = (
            select(DailyEntryRow)
            .where(DailyEntryRow.entry_date >= start)
            .where(DailyEntryRow.entry_date <= end)
        )
        if user_id is not None:
            stmt = stmt.where(DailyEntryRow.user_id == user_id)
        if kinds:
            real_kinds = [k for k in kinds if k != ARTIFACT_KIND]
            if real_kinds:
                stmt = stmt.where(DailyEntryRow.kind.in_(real_kinds))
            else:
                # Only artifact_ref was requested: no real rows count.
                return synthetic_count if include_artifacts else 0
        if statuses:
            stmt = stmt.where(DailyEntryRow.status.in_(list(statuses)))
        if q:
            like = f"%{q.strip().lower()}%"
            stmt = stmt.where(func.lower(DailyEntryRow.title).like(like))

        all_rows = list(self.session.exec(stmt))
        if tags:
            wanted = set(tags)
            all_rows = [r for r in all_rows if wanted.issubset(set(r.tags or []))]

        real_total = len(all_rows)
        if include_artifacts:
            return real_total + synthetic_count
        return real_total

    def _synthesize_artifacts(
        self,
        *,
        start: date,
        end: date,
        tz: ZoneInfo,
    ) -> list[dict[str, Any]]:
        """Build synthetic ``artifact_ref`` items from zettels, captures, reviews.

        Source ``created_at`` (UTC) is converted to tz-local date for the
        ``entry_date`` field. Items are never stored - always derived.
        """
        start_utc, end_utc = _range_window(start, end, tz)
        items: list[dict[str, Any]] = []

        items.extend(self._artifacts_from_zettels(start, end, start_utc, end_utc, tz))
        items.extend(self._artifacts_from_captures(start, end, start_utc, end_utc, tz))
        items.extend(self._artifacts_from_reviews(start, end, start_utc, end_utc, tz))

        return items

    def _artifacts_from_zettels(
        self,
        start: date,
        end: date,
        start_utc: datetime,
        end_utc: datetime,
        tz: ZoneInfo,
    ) -> list[dict[str, Any]]:
        try:
            rows = list(
                self.session.exec(
                    select(ZettelCard)
                    .where(ZettelCard.created_at >= start_utc)
                    .where(ZettelCard.created_at < end_utc)
                    .order_by(ZettelCard.created_at.desc())
                    .limit(_MAX_ARTIFACT_ROWS_PER_SOURCE)
                )
            )
        except Exception:  # pragma: no cover - table missing
            return []
        out: list[dict[str, Any]] = []
        for card in rows:
            if card.id is None:
                continue
            local_day = _local_date(card.created_at, tz)
            if local_day is None or local_day < start or local_day > end:
                continue
            out.append(
                _build_artifact(
                    ref_kind="zettel",
                    ref_id=card.id,
                    ref_url=f"/zettels/{card.id}",
                    entry_date=local_day,
                    title=card.title or "Untitled zettel",
                    tags=list(card.tags or []),
                    created_at=card.created_at,
                    updated_at=card.updated_at,
                )
            )
        return out

    def _artifacts_from_captures(
        self,
        start: date,
        end: date,
        start_utc: datetime,
        end_utc: datetime,
        tz: ZoneInfo,
    ) -> list[dict[str, Any]]:
        try:
            rows = list(
                self.session.exec(
                    select(DocumentRow)
                    .where(DocumentRow.created_at >= start_utc)
                    .where(DocumentRow.created_at < end_utc)
                    .order_by(DocumentRow.created_at.desc())
                    .limit(_MAX_ARTIFACT_ROWS_PER_SOURCE)
                )
            )
        except Exception:  # pragma: no cover - table missing
            return []
        out: list[dict[str, Any]] = []
        for doc in rows:
            if doc.id is None:
                continue
            local_day = _local_date(doc.created_at, tz)
            if local_day is None or local_day < start or local_day > end:
                continue
            out.append(
                _build_artifact(
                    ref_kind="capture",
                    ref_id=str(doc.id),
                    ref_url=f"/documents/{doc.id}",
                    entry_date=local_day,
                    title=doc.title or "Untitled capture",
                    tags=list(doc.tags or []),
                    created_at=doc.created_at,
                    updated_at=doc.updated_at,
                )
            )
        return out

    def _artifacts_from_reviews(
        self,
        start: date,
        end: date,
        start_utc: datetime,
        end_utc: datetime,
        tz: ZoneInfo,
    ) -> list[dict[str, Any]]:
        try:
            rows = list(
                self.session.exec(
                    select(ZettelReview)
                    .where(ZettelReview.created_at >= start_utc)
                    .where(ZettelReview.created_at < end_utc)
                    .order_by(ZettelReview.created_at.desc())
                    .limit(_MAX_ARTIFACT_ROWS_PER_SOURCE)
                )
            )
        except Exception:  # pragma: no cover - table missing
            return []
        card_ids = [r.card_id for r in rows if r.card_id is not None]
        titles: dict[int, str] = {}
        if card_ids:
            try:
                cards = list(
                    self.session.exec(select(ZettelCard).where(ZettelCard.id.in_(card_ids)))
                )
                titles = {c.id: c.title for c in cards if c.id is not None}
            except Exception:  # pragma: no cover
                titles = {}
        out: list[dict[str, Any]] = []
        for review in rows:
            if review.id is None:
                continue
            local_day = _local_date(review.created_at, tz)
            if local_day is None or local_day < start or local_day > end:
                continue
            card_title = titles.get(review.card_id, "Review")
            out.append(
                _build_artifact(
                    ref_kind="review",
                    ref_id=review.id,
                    ref_url=f"/zettels/{review.card_id}/reviews/{review.id}",
                    entry_date=local_day,
                    title=f"Review: {card_title}",
                    tags=[],
                    created_at=review.created_at,
                    updated_at=review.updated_at,
                )
            )
        return out


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_real(row: DailyEntryRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "entry_date": row.entry_date.isoformat() if row.entry_date else None,
        "title": row.title,
        "body_md": row.body_md or "",
        "status": row.status,
        "priority": row.priority,
        "tags": list(row.tags or []),
        "meta": dict(row.meta or {}),
        "created_at": _to_iso(row.created_at),
        "updated_at": _to_iso(row.updated_at),
        "is_synthetic": False,
    }


def _build_artifact(
    *,
    ref_kind: str,
    ref_id: int | str,
    ref_url: str,
    entry_date: date,
    title: str,
    tags: list[str],
    created_at: datetime | None,
    updated_at: datetime | None,
) -> dict[str, Any]:
    return {
        "id": f"{ref_kind}:{ref_id}",
        "kind": ARTIFACT_KIND,
        "entry_date": entry_date.isoformat(),
        "title": title,
        "body_md": "",
        "status": None,
        "priority": 0,
        "tags": list(tags or []),
        "meta": {
            "ref_kind": ref_kind,
            "ref_id": ref_id,
            "ref_url": ref_url,
        },
        "created_at": _to_iso(created_at),
        "updated_at": _to_iso(updated_at),
        "is_synthetic": True,
    }


def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
    """Primary: entry_date DESC. Secondary: created_at DESC."""
    return (item.get("entry_date") or "", item.get("created_at") or "")


__all__ = [
    "ARTIFACT_KIND",
    "EntriesPage",
    "EntryService",
    "VALID_KINDS",
    "VALID_STATUSES",
]
