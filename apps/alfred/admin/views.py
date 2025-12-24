"""SQLAdmin view registrations."""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqladmin import BaseView, ModelView, action, expose
from sqlalchemy import update

from alfred.core.database import SessionLocal
from alfred.models import CompanyInterviewRow, LearningTopic, User, ZettelCard
from alfred.schemas.zettel import ZettelCardCreate
from alfred.services.zettelkasten_service import ZettelkastenService


class ZettelCardAdmin(ModelView, model=ZettelCard):
    """CRUD + bulk actions for knowledge cards."""

    name = "Zettel Cards"
    icon = "fa-regular fa-note-sticky"

    column_list = [
        ZettelCard.id,
        ZettelCard.title,
        ZettelCard.topic,
        ZettelCard.tags,
        ZettelCard.importance,
        ZettelCard.confidence,
        ZettelCard.status,
        ZettelCard.updated_at,
    ]
    column_searchable_list = [ZettelCard.title, ZettelCard.summary, ZettelCard.topic]
    column_sortable_list = column_list
    column_default_sort = ("updated_at", True)  # desc

    form_excluded_columns = ["created_at", "updated_at", "embedding"]

    can_export = True
    column_export_list = [
        ZettelCard.id,
        ZettelCard.title,
        ZettelCard.topic,
        ZettelCard.tags,
        ZettelCard.importance,
        ZettelCard.confidence,
        ZettelCard.status,
        ZettelCard.created_at,
        ZettelCard.updated_at,
    ]

    @action(
        name="archive",
        label="Archive selected",
        confirmation_message="Archive selected cards?",
        add_in_list=True,
        add_in_detail=False,
    )
    async def archive_selected(self, request: Request) -> RedirectResponse:
        ids = _selected_ids(request.query_params.get("pks"))
        if not ids:
            return RedirectResponse(
                request.url_for("admin:list", identity=self.identity), status_code=303
            )

        with SessionLocal() as session:
            session.execute(
                update(ZettelCard).where(ZettelCard.id.in_(ids)).values(status="archived")
            )
            session.commit()

        return RedirectResponse(
            request.url_for("admin:list", identity=self.identity), status_code=303
        )


class LearningTopicAdmin(ModelView, model=LearningTopic):
    """Admin for learning topics."""

    name = "Learning Topics"
    icon = "fa-solid fa-graduation-cap"

    column_list = [
        LearningTopic.id,
        LearningTopic.name,
        LearningTopic.status,
        LearningTopic.progress,
        LearningTopic.tags,
        LearningTopic.updated_at,
    ]
    column_searchable_list = [LearningTopic.name, LearningTopic.description]
    column_sortable_list = column_list
    column_default_sort = ("updated_at", True)

    can_export = True
    column_export_list = column_list + [
        LearningTopic.created_at,
        LearningTopic.interview_at,
        LearningTopic.first_learned_at,
        LearningTopic.last_studied_at,
    ]


class CompanyInterviewAdmin(ModelView, model=CompanyInterviewRow):
    """Read-only admin for scraped interview rows."""

    name = "Company Interviews"
    icon = "fa-solid fa-building"

    column_list = [
        CompanyInterviewRow.id,
        CompanyInterviewRow.company,
        CompanyInterviewRow.role,
        CompanyInterviewRow.location,
        CompanyInterviewRow.provider,
        CompanyInterviewRow.interview_date,
        CompanyInterviewRow.updated_at,
    ]
    column_searchable_list = [
        CompanyInterviewRow.company,
        CompanyInterviewRow.role,
        CompanyInterviewRow.location,
        CompanyInterviewRow.provider,
    ]
    column_sortable_list = column_list
    column_default_sort = ("updated_at", True)

    can_create = False
    can_edit = False
    can_delete = False
    can_export = True


class UserAdmin(ModelView, model=User):
    """Admin for application users."""

    name = "Users"
    icon = "fa-solid fa-user"

    column_list = [
        User.id,
        User.email,
        User.full_name,
        User.is_active,
        User.is_superuser,
        User.created_at,
    ]
    column_searchable_list = [User.email, User.full_name]
    column_sortable_list = column_list
    column_default_sort = ("created_at", True)

    form_excluded_columns = ["created_at", "updated_at"]
    can_export = True


class ZettelCardImportView(BaseView):
    """CSV → ZettelCard importer (simple, synchronous)."""

    name = "Import Zettel CSV"
    icon = "fa-solid fa-file-csv"

    @expose("/admin/import/zettels", methods=["GET"])
    async def form(self, request: Request) -> HTMLResponse:  # noqa: D401
        html = """
        <h2>Import Zettel Cards (CSV)</h2>
        <p>Columns: title (required), content, summary, tags (comma-separated), topic, source_url,
        document_id, importance, confidence, status</p>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required />
            <button type="submit">Upload</button>
        </form>
        """
        return HTMLResponse(html)

    @expose("/admin/import/zettels", methods=["POST"])
    async def upload(self, request: Request) -> HTMLResponse:
        form = await request.form()
        file: UploadFile | None = form.get("file")  # type: ignore[assignment]
        if file is None:
            return HTMLResponse("<p>No file provided</p>", status_code=400)

        content = (await file.read()).decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))

        created = 0
        errors: list[str] = []
        with SessionLocal() as session:
            service = ZettelkastenService(session)
            for idx, row in enumerate(reader, start=1):
                parsed = _normalize_row(row)
                try:
                    payload = ZettelCardCreate(**parsed)
                except Exception as exc:  # pylint: disable=broad-except
                    errors.append(f"Row {idx}: {exc}")
                    continue
                try:
                    service.create_card(**payload.model_dump())
                    created += 1
                except Exception as exc:  # pragma: no cover - db errors
                    errors.append(f"Row {idx}: failed to insert ({exc})")

        html = [
            f"<p>Inserted {created} cards.</p>",
            "<p>Go back to <a href='/admin/zettelcard/list'>Zettel cards</a>.</p>",
        ]
        if errors:
            html.append("<h4>Errors</h4><ul>")
            html.extend(f"<li>{e}</li>" for e in errors)
            html.append("</ul>")
        return HTMLResponse("".join(html))


def _selected_ids(pks: str | None) -> list[int]:
    if not pks:
        return []
    return [int(x) for x in pks.split(",") if x]


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert CSV row values into a ZettelCardCreate-friendly dict."""
    tags = row.get("tags")
    tags_list: list[str] | None = None
    if tags:
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]

    def _clean(key: str) -> str | None:
        val = row.get(key)
        return val.strip() if isinstance(val, str) and val.strip() else None

    parsed: dict[str, Any] = {
        "title": row.get("title") or "",
        "content": _clean("content"),
        "summary": _clean("summary"),
        "tags": tags_list,
        "topic": _clean("topic"),
        "source_url": _clean("source_url"),
        "document_id": _clean("document_id"),
        "status": row.get("status") or "active",
    }

    if "importance" in row and row["importance"] not in (None, ""):
        parsed["importance"] = int(float(row["importance"]))
    if "confidence" in row and row["confidence"] not in (None, ""):
        parsed["confidence"] = float(row["confidence"])

    return parsed


__all__ = [
    "ZettelCardAdmin",
    "LearningTopicAdmin",
    "CompanyInterviewAdmin",
    "ZettelCardImportView",
]
