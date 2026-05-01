"""CRUD for :class:`DailyReflectionRow` with idempotent upsert."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlmodel import Session, select

from alfred.models.today import DailyReflectionRow
from alfred.services.today.pipeline import DailyContext


@dataclass
class ReflectionService:
    session: Session

    def get_for_date(
        self,
        entry_date: date,
        *,
        user_id: str | None = None,
    ) -> DailyReflectionRow | None:
        stmt = select(DailyReflectionRow).where(DailyReflectionRow.entry_date == entry_date)
        if user_id is not None:
            stmt = stmt.where(DailyReflectionRow.user_id == user_id)
        return self.session.exec(stmt).first()

    def upsert_for_date(
        self,
        *,
        ctx: DailyContext,
        stages_ran: list[str],
    ) -> DailyReflectionRow:
        """Idempotent — same ``entry_date`` re-run overwrites the row in place.

        DB-level uniqueness is enforced by ``ix_daily_reflections_date``
        (unique). We do a read-then-write rather than an ``ON CONFLICT``
        because SQLModel does not natively expose upsert; this is safe under
        the Redis lock the Celery task wraps the whole pipeline in (see T12).
        """
        existing = self.get_for_date(ctx.entry_date, user_id=ctx.user_id)

        digest_md = str(ctx.artifacts.get("digest_md") or "")
        stats: dict = dict(ctx.artifacts.get("stats") or {})
        stats.setdefault("version", 1)
        stats.setdefault(
            "entry_counts",
            {
                "todo": sum(1 for e in ctx.entries if e.kind == "todo"),
                "todo_done": sum(1 for e in ctx.entries if e.kind == "todo" and e.status == "done"),
                "note": sum(1 for e in ctx.entries if e.kind == "note"),
                "learning": sum(1 for e in ctx.entries if e.kind == "learning"),
                "artifact_ref": len(ctx.zettels_created)
                + len(ctx.captures)
                + len(ctx.reviews_completed),
            },
        )
        stats.setdefault("zettels_created", len(ctx.zettels_created))
        stats.setdefault("captures_ingested", len(ctx.captures))
        stats.setdefault("reviews_completed", len(ctx.reviews_completed))
        stats.setdefault("carryover_count", int(ctx.artifacts.get("carryover_count") or 0))
        if ctx.errors:
            stats["errors"] = ctx.errors

        # Store naive UTC to match the rest of the codebase's DateTime columns.
        now = datetime.now(UTC).replace(tzinfo=None)

        if existing is None:
            row = DailyReflectionRow(
                entry_date=ctx.entry_date,
                user_id=ctx.user_id,
                digest_md=digest_md,
                stats=stats,
                pipeline_run_id=ctx.run_id,
                stages_ran=list(stages_ran),
                generated_at=now,
            )
            self.session.add(row)
        else:
            existing.digest_md = digest_md
            existing.stats = stats
            existing.pipeline_run_id = ctx.run_id
            existing.stages_ran = list(stages_ran)
            existing.generated_at = now
            self.session.add(existing)
            row = existing

        self.session.commit()
        self.session.refresh(row)
        return row


__all__ = ["ReflectionService"]
