"""Domain service for Alfred Notes (hierarchical markdown-first pages)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import sqlalchemy as sa
from sqlmodel import Session, select

from alfred.core.exceptions import AlfredException, NotFoundError
from alfred.core.utils import clamp_int, utcnow
from alfred.models.notes import NoteRow, WorkspaceRow


class WorkspaceNotFoundError(NotFoundError):
    default_code = "workspace_not_found"


class NoteNotFoundError(NotFoundError):
    default_code = "note_not_found"


class NoteMoveConflictError(AlfredException):
    """Raised when a note move would violate hierarchy constraints."""

    status_code = 409
    default_code = "note_move_conflict"


def _as_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except Exception as exc:
        raise ValueError(f"Invalid UUID: {value}") from exc


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _scalar_one(value: object) -> object:
    """Return the first column from a SQLAlchemy/SQLModel scalar row result."""

    try:
        return value[0]  # type: ignore[index]
    except Exception:
        return value


@dataclass(slots=True)
class NotesService:
    """CRUD + hierarchy operations for Alfred Notes."""

    session: Session

    # ---------------
    # Workspaces
    # ---------------
    def get_workspace(self, workspace_id: str | uuid.UUID) -> WorkspaceRow:
        wid = _as_uuid(str(workspace_id))
        if wid is None:
            raise ValueError("workspace_id is required")
        row = self.session.get(WorkspaceRow, wid)
        if row is None:
            raise WorkspaceNotFoundError(f"Workspace not found: {wid}")
        return row

    def list_workspaces(self, *, user_id: int | None = None) -> list[WorkspaceRow]:
        stmt = select(WorkspaceRow).order_by(
            sa.desc(WorkspaceRow.updated_at), WorkspaceRow.id.asc()
        )
        if user_id is not None:
            stmt = stmt.where(WorkspaceRow.user_id == user_id)
        return list(self.session.exec(stmt).all())

    def get_or_create_default_workspace(self, *, user_id: int | None = None) -> WorkspaceRow:
        """Return a stable default workspace for a user (or anonymous)."""

        stmt = (
            select(WorkspaceRow)
            .where(WorkspaceRow.user_id == user_id)
            .where(WorkspaceRow.name == "Personal")
            .order_by(WorkspaceRow.created_at.asc())
        )
        existing = self.session.exec(stmt).first()
        if existing is not None:
            return existing

        now = utcnow()
        created = WorkspaceRow(
            name="Personal",
            icon="📓",
            user_id=user_id,
            settings={"default": True},
            created_at=now,
            updated_at=now,
        )
        self.session.add(created)
        self.session.commit()
        self.session.refresh(created)
        return created

    def create_workspace(
        self,
        *,
        name: str,
        icon: str | None = None,
        user_id: int | None = None,
        settings: dict | None = None,  # noqa: ANN401 - passthrough JSON
    ) -> WorkspaceRow:
        trimmed_name = (name or "").strip()
        if not trimmed_name:
            raise ValueError("name is required")

        now = utcnow()
        row = WorkspaceRow(
            name=trimmed_name,
            icon=_strip_or_none(icon),
            user_id=user_id,
            settings=dict(settings or {}),
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    # ---------------
    # Notes
    # ---------------
    def get_note(self, note_id: str | uuid.UUID, *, include_archived: bool = False) -> NoteRow:
        nid = _as_uuid(str(note_id))
        if nid is None:
            raise ValueError("note_id is required")
        row = self.session.get(NoteRow, nid)
        if row is None or (row.is_archived and not include_archived):
            raise NoteNotFoundError(f"Note not found: {nid}")
        return row

    def list_notes(
        self,
        *,
        workspace_id: str | uuid.UUID,
        q: str | None = None,
        parent_id: str | uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
        include_archived: bool = False,
    ) -> tuple[list[NoteRow], int]:
        wid = _as_uuid(str(workspace_id))
        if wid is None:
            raise ValueError("workspace_id is required")

        limit = clamp_int(int(limit), lo=1, hi=200)
        skip = max(0, int(skip))
        parent_uuid = _as_uuid(str(parent_id)) if parent_id is not None else None

        stmt = select(NoteRow).where(NoteRow.workspace_id == wid)
        count_stmt = select(sa.func.count()).select_from(NoteRow).where(NoteRow.workspace_id == wid)

        if not include_archived:
            stmt = stmt.where(NoteRow.is_archived.is_(False))
            count_stmt = count_stmt.where(NoteRow.is_archived.is_(False))

        if parent_id is not None:
            stmt = stmt.where(NoteRow.parent_id == parent_uuid)
            count_stmt = count_stmt.where(NoteRow.parent_id == parent_uuid)
            stmt = stmt.order_by(NoteRow.position.asc(), sa.desc(NoteRow.updated_at))
        else:
            stmt = stmt.order_by(sa.desc(NoteRow.updated_at))

        if q and q.strip():
            like = f"%{q.strip()}%"
            stmt = stmt.where(NoteRow.title.ilike(like) | NoteRow.content_markdown.ilike(like))
            count_stmt = count_stmt.where(
                NoteRow.title.ilike(like) | NoteRow.content_markdown.ilike(like)
            )

        stmt = stmt.offset(skip).limit(limit)

        items = list(self.session.exec(stmt).all())
        total_row = self.session.exec(count_stmt).one()
        total = int(_scalar_one(total_row))
        return items, total

    def create_note(
        self,
        *,
        workspace_id: str | uuid.UUID | None = None,
        parent_id: str | uuid.UUID | None = None,
        title: str | None = None,
        icon: str | None = None,
        cover_image: str | None = None,
        content_markdown: str | None = None,
        content_json: dict | None = None,  # noqa: ANN401 - JSON payload
        user_id: int | None = None,
    ) -> NoteRow:
        workspace = (
            self.get_workspace(workspace_id)
            if workspace_id is not None
            else self.get_or_create_default_workspace(user_id=user_id)
        )

        parent_uuid = _as_uuid(str(parent_id)) if parent_id is not None else None
        if parent_uuid is not None:
            parent = self.session.get(NoteRow, parent_uuid)
            if parent is None or parent.is_archived:
                raise NoteNotFoundError(f"Parent note not found: {parent_uuid}")
            if parent.workspace_id != workspace.id:
                raise NoteMoveConflictError("Parent note is in a different workspace")

        max_pos_stmt = (
            select(sa.func.max(NoteRow.position))
            .where(NoteRow.workspace_id == workspace.id)
            .where(NoteRow.parent_id == parent_uuid)
            .where(NoteRow.is_archived.is_(False))
        )
        max_pos_row = self.session.exec(max_pos_stmt).one()
        max_pos_value = _scalar_one(max_pos_row)
        next_pos = (int(max_pos_value) if max_pos_value is not None else -1) + 1

        now = utcnow()
        row = NoteRow(
            title=((title or "").strip() or "Untitled"),
            icon=_strip_or_none(icon),
            cover_image=_strip_or_none(cover_image),
            parent_id=parent_uuid,
            workspace_id=workspace.id,
            position=next_pos,
            content_markdown=content_markdown or "",
            content_json=dict(content_json) if content_json is not None else None,
            created_at=now,
            updated_at=now,
            created_by=user_id,
            last_edited_by=user_id,
            is_archived=False,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def update_note(
        self,
        note_id: str | uuid.UUID,
        *,
        title: str | None = None,
        icon: str | None = None,
        cover_image: str | None = None,
        content_markdown: str | None = None,
        content_json: dict | None = None,  # noqa: ANN401 - JSON payload
        is_archived: bool | None = None,
        user_id: int | None = None,
    ) -> NoteRow:
        row = self.get_note(note_id, include_archived=True)

        if title is not None:
            trimmed = title.strip()
            if not trimmed:
                raise ValueError("title must not be empty")
            row.title = trimmed
        if icon is not None:
            row.icon = _strip_or_none(icon)
        if cover_image is not None:
            row.cover_image = _strip_or_none(cover_image)
        if content_markdown is not None:
            row.content_markdown = content_markdown
        if content_json is not None:
            row.content_json = dict(content_json)
        if is_archived is not None:
            row.is_archived = bool(is_archived)

        row.updated_at = utcnow()
        if user_id is not None:
            row.last_edited_by = user_id
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def archive_note(self, note_id: str | uuid.UUID, *, user_id: int | None = None) -> NoteRow:
        return self.update_note(note_id, is_archived=True, user_id=user_id)

    def list_children(
        self,
        note_id: str | uuid.UUID,
        *,
        include_archived: bool = False,
    ) -> list[NoteRow]:
        note = self.get_note(note_id, include_archived=True)
        stmt = (
            select(NoteRow)
            .where(NoteRow.workspace_id == note.workspace_id)
            .where(NoteRow.parent_id == note.id)
            .order_by(NoteRow.position.asc(), NoteRow.id.asc())
        )
        if not include_archived:
            stmt = stmt.where(NoteRow.is_archived.is_(False))
        return list(self.session.exec(stmt).all())

    def _assert_no_cycle(self, *, moving: NoteRow, new_parent_id: uuid.UUID | None) -> None:
        if new_parent_id is None:
            return
        if new_parent_id == moving.id:
            raise NoteMoveConflictError("A note cannot be its own parent")

        seen: set[uuid.UUID] = set()
        current = new_parent_id
        while current is not None:
            if current in seen:
                raise NoteMoveConflictError("Cycle detected while validating move")
            seen.add(current)
            if current == moving.id:
                raise NoteMoveConflictError("Cannot move a note into its own descendant")
            parent = self.session.get(NoteRow, current)
            if parent is None:
                raise NoteNotFoundError(f"Parent note not found: {current}")
            current = parent.parent_id

    def _siblings(
        self, *, workspace_id: uuid.UUID, parent_id: uuid.UUID | None, include_archived: bool
    ) -> list[NoteRow]:
        stmt = (
            select(NoteRow)
            .where(NoteRow.workspace_id == workspace_id)
            .where(NoteRow.parent_id == parent_id)
            .order_by(NoteRow.position.asc(), NoteRow.created_at.asc(), NoteRow.id.asc())
        )
        if not include_archived:
            stmt = stmt.where(NoteRow.is_archived.is_(False))
        return list(self.session.exec(stmt).all())

    def move_note(
        self,
        note_id: str | uuid.UUID,
        *,
        parent_id: str | uuid.UUID | None,
        position: int | None = None,
        user_id: int | None = None,
    ) -> NoteRow:
        row = self.get_note(note_id, include_archived=True)
        if row.is_archived:
            raise NoteMoveConflictError("Cannot move an archived note")

        new_parent_uuid = _as_uuid(str(parent_id)) if parent_id is not None else None

        if new_parent_uuid is not None:
            parent = self.session.get(NoteRow, new_parent_uuid)
            if parent is None or parent.is_archived:
                raise NoteNotFoundError(f"Parent note not found: {new_parent_uuid}")
            if parent.workspace_id != row.workspace_id:
                raise NoteMoveConflictError("Parent note is in a different workspace")

        self._assert_no_cycle(moving=row, new_parent_id=new_parent_uuid)

        if row.parent_id == new_parent_uuid and position is None:
            return row

        old_parent_id = row.parent_id
        workspace_id = row.workspace_id

        if old_parent_id == new_parent_uuid:
            siblings = [
                n
                for n in self._siblings(
                    workspace_id=workspace_id, parent_id=old_parent_id, include_archived=False
                )
                if n.id != row.id
            ]
            insert_at = clamp_int(
                position if position is not None else len(siblings), lo=0, hi=len(siblings)
            )
            siblings.insert(insert_at, row)
            for idx, note in enumerate(siblings):
                if note.position != idx:
                    note.position = idx
                note.parent_id = new_parent_uuid
                self.session.add(note)
        else:
            old_siblings = [
                n
                for n in self._siblings(
                    workspace_id=workspace_id, parent_id=old_parent_id, include_archived=False
                )
                if n.id != row.id
            ]
            for idx, note in enumerate(old_siblings):
                if note.position != idx:
                    note.position = idx
                    self.session.add(note)

            new_siblings = self._siblings(
                workspace_id=workspace_id, parent_id=new_parent_uuid, include_archived=False
            )
            insert_at = clamp_int(
                position if position is not None else len(new_siblings),
                lo=0,
                hi=len(new_siblings),
            )
            new_siblings.insert(insert_at, row)
            for idx, note in enumerate(new_siblings):
                note.parent_id = new_parent_uuid
                if note.position != idx:
                    note.position = idx
                self.session.add(note)

        row.updated_at = utcnow()
        if user_id is not None:
            row.last_edited_by = user_id
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def tree(
        self,
        *,
        workspace_id: str | uuid.UUID,
        include_archived: bool = False,
    ) -> list[NoteRow]:
        wid = _as_uuid(str(workspace_id))
        if wid is None:
            raise ValueError("workspace_id is required")

        stmt = select(NoteRow).where(NoteRow.workspace_id == wid)
        if not include_archived:
            stmt = stmt.where(NoteRow.is_archived.is_(False))
        return list(self.session.exec(stmt).all())


__all__ = [
    "NoteMoveConflictError",
    "NoteNotFoundError",
    "NotesService",
    "WorkspaceNotFoundError",
]
