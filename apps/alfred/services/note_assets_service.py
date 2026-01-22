"""Domain service for Alfred Notes assets (images, screenshots, attachments)."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session

from alfred.core.exceptions import BadRequestError, NotFoundError
from alfred.core.utils import utcnow
from alfred.models.notes import NoteAssetRow, NoteRow
from alfred.services.notes_service import NoteNotFoundError


class NoteAssetNotFoundError(NotFoundError):
    default_code = "note_asset_not_found"


class NoteAssetTooLargeError(BadRequestError):
    default_code = "note_asset_too_large"
    status_code = 413


class NoteAssetUnsupportedTypeError(BadRequestError):
    default_code = "note_asset_unsupported_type"
    status_code = 415


ALLOWED_IMAGE_MIME_TYPES: set[str] = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}

MAX_NOTE_ASSET_BYTES = 10 * 1024 * 1024


def _default_file_name(*, mime_type: str, sha256: str) -> str:
    ext = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(mime_type, "")
    return f"image-{sha256[:12]}{ext}"


def _strip_or_default(value: str | None, *, default: str) -> str:
    if value is None:
        return default
    trimmed = value.strip()
    return trimmed or default


@dataclass(slots=True)
class NoteAssetsService:
    """Store and retrieve assets that are embedded inside notes."""

    session: Session

    def create_image_asset(
        self,
        note_id: uuid.UUID,
        *,
        file_name: str | None,
        mime_type: str,
        data: bytes,
        user_id: int | None = None,
    ) -> NoteAssetRow:
        """Persist an uploaded image and associate it with a note."""

        note = self.session.get(NoteRow, note_id)
        if note is None or note.is_archived:
            raise NoteNotFoundError(f"Note not found: {note_id}")

        if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise NoteAssetUnsupportedTypeError(f"Unsupported mime type: {mime_type}")

        size = len(data)
        if size <= 0:
            raise ValueError("Empty upload")
        if size > MAX_NOTE_ASSET_BYTES:
            raise NoteAssetTooLargeError(
                f"Asset too large ({size} bytes). Max is {MAX_NOTE_ASSET_BYTES} bytes."
            )

        sha = hashlib.sha256(data).hexdigest()
        resolved_name = _strip_or_default(
            file_name,
            default=_default_file_name(mime_type=mime_type, sha256=sha),
        )

        now: datetime = utcnow()
        row = NoteAssetRow(
            note_id=note.id,
            workspace_id=note.workspace_id,
            file_name=resolved_name,
            mime_type=mime_type,
            size_bytes=size,
            sha256=sha,
            data=data,
            created_at=now,
            created_by=user_id,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_asset(self, asset_id: uuid.UUID) -> NoteAssetRow:
        row = self.session.get(NoteAssetRow, asset_id)
        if row is None:
            raise NoteAssetNotFoundError(f"Note asset not found: {asset_id}")
        return row
