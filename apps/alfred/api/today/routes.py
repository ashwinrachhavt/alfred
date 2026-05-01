"""Today page API — serves the daily briefing."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel import Session, select

from alfred.api.dependencies import get_db_session
from alfred.models.today import DailyReflectionRow
from alfred.schemas.today import (
    DailyEntriesResponse,
    DailyEntryCreate,
    DailyEntryItem,
    DailyEntryUpdate,
    DailyReflectionResponse,
    PipelineRunRequest,
    PipelineRunResponse,
    TodayBriefingResponse,
    TodayCalendarResponse,
)
from alfred.services.today.entry_service import (
    ARTIFACT_KIND,
    VALID_KINDS,
    VALID_STATUSES,
    EntryService,
)
from alfred.services.today.reflection_service import ReflectionService

router = APIRouter(prefix="/api/today", tags=["today"])


@router.get("/briefing", response_model=TodayBriefingResponse)
def get_briefing(
    day: date | None = Query(default=None, alias="date"),
    tz: str = Query(default="UTC", min_length=1, max_length=64),
) -> TodayBriefingResponse:
    """Return a daily briefing for the requested date."""
    from alfred.tasks.daily_briefing import build_daily_briefing

    # Run synchronously for now — fast enough for single user
    return build_daily_briefing(target_date=day, tz_name=tz)


@router.get("/calendar", response_model=TodayCalendarResponse)
def get_calendar(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    days: int = Query(default=120, ge=28, le=366),
    tz: str = Query(default="UTC", min_length=1, max_length=64),
) -> TodayCalendarResponse:
    """Return day-level activity counts for calendar auditing."""
    from alfred.tasks.daily_briefing import build_today_calendar

    return build_today_calendar(
        start_date=start_date,
        end_date=end_date,
        days=days,
        tz_name=tz,
    )


# ---------------------------------------------------------------------------
# Daily entries CRUD (T3)
# ---------------------------------------------------------------------------


def _validate_kind_for_write(kind: str) -> None:
    """Route-layer guard: reject ``artifact_ref`` and unknown kinds.

    422 is the correct FastAPI convention for a validation error on input.
    """
    if kind == ARTIFACT_KIND:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"kind={kind!r} is synthesized at read time and cannot be "
                "created or updated directly"
            ),
        )
    if kind not in VALID_KINDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid kind {kind!r}; must be one of {sorted(VALID_KINDS)}",
        )


def _validate_status_for_write(status_value: str) -> None:
    if status_value not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"invalid status {status_value!r}; must be one of " f"{sorted(VALID_STATUSES)}"
            ),
        )


@router.get("/entries", response_model=DailyEntriesResponse)
def list_entries(
    start: date = Query(..., alias="start"),
    end: date = Query(...),
    tz: str = Query(default="UTC", min_length=1, max_length=64),
    kind: list[str] | None = Query(default=None),
    status_filter: list[str] | None = Query(default=None, alias="status"),
    tag: list[str] | None = Query(default=None),
    q: str | None = Query(default=None),
    include_artifacts: bool = Query(default=True),
    limit: int = Query(default=500, ge=1, le=2000),
    cursor: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> DailyEntriesResponse:
    """List daily entries for a date range, with optional filters.

    Mixes real rows and synthesized ``artifact_ref`` rows; disable by
    passing ``include_artifacts=false``.
    """
    service = EntryService(session=session)
    try:
        page = service.list_entries(
            start=start,
            end=end,
            tz_name=tz,
            kinds=kind,
            statuses=status_filter,
            tags=tag,
            q=q,
            include_artifacts=include_artifacts,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    items = [DailyEntryItem.model_validate(entry) for entry in page.entries]
    return DailyEntriesResponse(
        entries=items,
        next_cursor=page.next_cursor,
        total=page.total,
    )


@router.post(
    "/entries",
    response_model=DailyEntryItem,
    status_code=status.HTTP_201_CREATED,
)
def create_entry(
    payload: DailyEntryCreate,
    session: Session = Depends(get_db_session),
) -> DailyEntryItem:
    """Create a daily entry. ``kind`` must be one of todo/note/learning."""
    _validate_kind_for_write(payload.kind)
    _validate_status_for_write(payload.status)

    service = EntryService(session=session)
    try:
        row = service.create_entry(
            entry_date=payload.entry_date,
            kind=payload.kind,
            title=payload.title,
            body_md=payload.body_md,
            status=payload.status,
            priority=payload.priority,
            tags=payload.tags,
            meta=payload.meta,
            user_id=payload.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return DailyEntryItem(
        id=row.id,
        kind=row.kind,
        entry_date=row.entry_date.isoformat() if row.entry_date else "",
        title=row.title,
        body_md=row.body_md or "",
        status=row.status,
        priority=row.priority,
        tags=list(row.tags or []),
        meta=dict(row.meta or {}),
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
        is_synthetic=False,
    )


@router.patch("/entries/{entry_id}", response_model=DailyEntryItem)
def update_entry(
    entry_id: int,
    payload: DailyEntryUpdate,
    session: Session = Depends(get_db_session),
) -> DailyEntryItem:
    """Partially update a daily entry. Only provided fields are touched."""
    patch = payload.model_dump(exclude_unset=True)

    if "kind" in patch and patch["kind"] is not None:
        _validate_kind_for_write(patch["kind"])
    if "status" in patch and patch["status"] is not None:
        _validate_status_for_write(patch["status"])

    service = EntryService(session=session)

    # 404 before dispatching the patch so validation errors can't mask
    # "not found".
    if service.get_entry(entry_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    try:
        row = service.update_entry(entry_id, patch=patch)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found"
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=message,
        ) from exc

    return DailyEntryItem(
        id=row.id,
        kind=row.kind,
        entry_date=row.entry_date.isoformat() if row.entry_date else "",
        title=row.title,
        body_md=row.body_md or "",
        status=row.status,
        priority=row.priority,
        tags=list(row.tags or []),
        meta=dict(row.meta or {}),
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
        is_synthetic=False,
    )


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    session: Session = Depends(get_db_session),
) -> Response:
    """Delete a daily entry. 204 on success, 404 if missing."""
    service = EntryService(session=session)
    deleted = service.delete_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Daily reflections (T12)
# ---------------------------------------------------------------------------


@router.get("/reflections/{entry_date}", response_model=DailyReflectionResponse)
def get_reflection(
    entry_date: date,
    tz: str = Query(default="UTC", min_length=1, max_length=64),
    session: Session = Depends(get_db_session),
) -> DailyReflectionResponse:
    """Fetch the reflection row for a specific date. 404 if none."""
    row = ReflectionService(session=session).get_for_date(entry_date)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no reflection for {entry_date.isoformat()}",
        )
    return DailyReflectionResponse.from_row(row)


@router.get("/reflections", response_model=list[DailyReflectionResponse])
def list_reflections(
    start: date = Query(...),
    end: date = Query(...),
    tz: str = Query(default="UTC", min_length=1, max_length=64),
    session: Session = Depends(get_db_session),
) -> list[DailyReflectionResponse]:
    """List reflections in a date range (descending). Capped to 62 days
    to match the ``/entries`` window contract."""
    delta = (end - start).days
    if delta < 0 or delta > 62:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid date range (0..62 days)",
        )

    stmt = (
        select(DailyReflectionRow)
        .where(DailyReflectionRow.entry_date >= start)
        .where(DailyReflectionRow.entry_date <= end)
        .order_by(DailyReflectionRow.entry_date.desc())
    )
    rows = session.exec(stmt).all()
    return [DailyReflectionResponse.from_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Manual pipeline trigger (T12)
# ---------------------------------------------------------------------------


@router.post("/pipeline/run", response_model=PipelineRunResponse)
def trigger_pipeline(body: PipelineRunRequest) -> PipelineRunResponse:
    """Manually run or enqueue the Today pipeline for a specific date.

    Not auth-gated at PoC; idempotent via the Redis lock inside the task
    body. ``enqueue=False`` runs synchronously in-process (dev / small
    deployments); ``enqueue=True`` dispatches to Celery.
    """
    # Inline imports so the route module doesn't force celery/app-context
    # at import time during unit tests.
    from alfred.tasks.today_pipeline import _run
    from alfred.tasks.today_pipeline import run_for_date as _run_for_date_task

    if body.enqueue:
        async_result = _run_for_date_task.delay(
            entry_date=body.entry_date.isoformat(),
            tz_name=body.tz,
            user_id=body.user_id,
        )
        return PipelineRunResponse(dispatched=True, task_id=async_result.id)

    result = _run(body.entry_date, body.tz, body.user_id)
    return PipelineRunResponse(dispatched=False, result=result)
