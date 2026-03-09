"""Mixin: Quick-notes CRUD operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from alfred.models.doc_storage import QuickNoteRow
from alfred.schemas.documents import NoteCreate
from alfred.services.doc_storage.utils import (
    apply_offset_limit as _apply_offset_limit,
)
from alfred.services.doc_storage.utils import (
    parse_uuid as _parse_uuid,
)

from ._session import _session_scope


class NotesMixin:
    """Notes CRUD — mixed into DocStorageService."""

    session: Any  # provided by the dataclass host

    def create_note(self, note: NoteCreate) -> str:
        record = QuickNoteRow(
            text=note.text,
            source_url=note.source_url,
            meta=note.metadata or {},
        )
        with _session_scope(self.session) as s:
            s.add(record)
            s.commit()
            s.refresh(record)
            return str(record.id)

    def list_notes(self, *, q: str | None, skip: int, limit: int) -> dict[str, Any]:
        with _session_scope(self.session) as s:
            stmt = select(QuickNoteRow)
            if q:
                stmt = stmt.where(QuickNoteRow.text.ilike(f"%{q}%"))
            stmt = _apply_offset_limit(
                stmt.order_by(QuickNoteRow.created_at.desc()),
                skip=skip,
                limit=limit,
                max_limit=200,
            )
            items = s.exec(stmt).all()

            count_stmt = select(func.count()).select_from(QuickNoteRow)
            if q:
                count_stmt = count_stmt.where(QuickNoteRow.text.ilike(f"%{q}%"))
            total = s.exec(count_stmt).one()[0]

            return {
                "items": [
                    {
                        "id": str(n.id),
                        "text": n.text,
                        "source_url": n.source_url,
                        "metadata": n.meta or {},
                        "created_at": n.created_at,
                    }
                    for n in items
                ],
                "total": total,
                "skip": skip,
                "limit": limit,
            }

    def get_note(self, note_id: str) -> dict[str, Any] | None:
        uid = _parse_uuid(note_id)
        if uid is None:
            return None
        with _session_scope(self.session) as s:
            note = s.get(QuickNoteRow, uid)
            if not note:
                return None
            return {
                "id": str(note.id),
                "text": note.text,
                "source_url": note.source_url,
                "metadata": note.meta or {},
                "created_at": note.created_at,
            }

    def delete_note(self, note_id: str) -> bool:
        uid = _parse_uuid(note_id)
        if uid is None:
            return False
        with _session_scope(self.session) as s:
            note = s.get(QuickNoteRow, uid)
            if not note:
                return False
            s.delete(note)
            s.commit()
            return True
