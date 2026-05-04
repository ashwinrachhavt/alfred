"""Browse and import local filesystem content into Alfred Notes."""

from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from sqlmodel import Session

from alfred.core.exceptions import AlfredException, NotFoundError
from alfred.core.settings import settings
from alfred.services.notes_service import NotesService

MAX_IMPORT_FILE_BYTES = 512_000
DEFAULT_MAX_IMPORT_NOTES = 200
MAX_IMPORT_NOTES = 500
SKIPPED_RECURSIVE_DIRS = {
    ".git",
    ".hg",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}
SKIPPED_ENTRY_NAMES = {".DS_Store"}


class FilesystemPathNotAllowedError(AlfredException):
    status_code = 403
    default_code = "filesystem_path_not_allowed"


class FilesystemPathNotFoundError(NotFoundError):
    default_code = "filesystem_path_not_found"


def _allowed_roots() -> tuple[Path, ...]:
    """Return roots that the notes importer/browser can access."""

    roots = [
        Path.home().expanduser().resolve(),
        Path.cwd().resolve(),
        Path(settings.mcp_filesystem_path).expanduser().resolve(),
        Path(tempfile.gettempdir()).resolve(),
    ]
    for configured_root in settings.notes_filesystem_roots:
        raw_root = configured_root.strip()
        if raw_root:
            roots.append(Path(raw_root).expanduser().resolve(strict=False))

    unique_roots: list[Path] = []
    for root in roots:
        if root not in unique_roots:
            unique_roots.append(root)
    return tuple(unique_roots)


def _is_within_allowed_roots(path: Path) -> bool:
    for root in _allowed_roots():
        if path == root or root in path.parents:
            return True
    return False


@dataclass(slots=True)
class FilesystemEntry:
    name: str
    path: str
    kind: str
    hidden: bool
    importable: bool
    size_bytes: int | None = None
    reason: str | None = None


@dataclass(slots=True)
class FilesystemBrowseResult:
    path: str
    name: str
    parent_path: str | None
    root_path: str
    items: list[FilesystemEntry]


@dataclass(slots=True)
class FilesystemImportResult:
    source_path: str
    root_note_id: str
    imported_count: int
    skipped_count: int
    skipped_paths: list[str]


@dataclass(slots=True)
class UploadedFilesystemFile:
    relative_path: str
    content: bytes


@dataclass(slots=True)
class _ImportState:
    imported_count: int = 0
    skipped_paths: list[str] | None = None

    def __post_init__(self) -> None:
        if self.skipped_paths is None:
            self.skipped_paths = []


@dataclass(slots=True)
class NotesFilesystemService:
    """Filesystem browsing and note import helpers."""

    session: Session

    def browse(self, *, path: str | None = None) -> FilesystemBrowseResult:
        target = self._resolve_path(path)
        if target.is_file():
            raise ValueError("Browse expects a directory path")

        root = self._best_matching_root(target)
        parent_path = str(target.parent) if target != root and _is_within_allowed_roots(target.parent) else None

        items: list[FilesystemEntry] = []
        try:
            for entry in self._iter_entries(target):
                items.append(self._entry_for_browse(entry))
        except OSError as exc:
            raise ValueError(f"Unable to read directory: {target}") from exc

        return FilesystemBrowseResult(
            path=str(target),
            name=target.name or str(target),
            parent_path=parent_path,
            root_path=str(root),
            items=items,
        )

    def import_path(
        self,
        *,
        workspace_id: str | uuid.UUID,
        path: str,
        parent_id: str | uuid.UUID | None = None,
        user_id: int | None = None,
        max_files: int = DEFAULT_MAX_IMPORT_NOTES,
    ) -> FilesystemImportResult:
        target = self._resolve_path(path)
        notes = NotesService(self.session)

        max_notes = max(1, min(int(max_files), MAX_IMPORT_NOTES))
        state = _ImportState()

        if target.is_dir():
            if not self._has_importable_text_descendant(target):
                raise ValueError("No importable text files found in the selected folder")
            root_note = self._import_directory(
                target,
                notes=notes,
                workspace_id=workspace_id,
                parent_id=parent_id,
                user_id=user_id,
                state=state,
                max_notes=max_notes,
            )
        elif target.is_file():
            root_note = self._import_file(
                target,
                notes=notes,
                workspace_id=workspace_id,
                parent_id=parent_id,
                user_id=user_id,
                state=state,
                max_notes=max_notes,
            )
        else:
            raise ValueError("Only files and directories can be imported")

        if root_note is None:
            raise ValueError("The selected file cannot be imported into notes")

        return FilesystemImportResult(
            source_path=str(target),
            root_note_id=str(root_note.id),
            imported_count=state.imported_count,
            skipped_count=len(state.skipped_paths or []),
            skipped_paths=list(state.skipped_paths or []),
        )

    def import_upload(
        self,
        *,
        workspace_id: str | uuid.UUID,
        files: list[UploadedFilesystemFile],
        parent_id: str | uuid.UUID | None = None,
        user_id: int | None = None,
        max_files: int = DEFAULT_MAX_IMPORT_NOTES,
    ) -> FilesystemImportResult:
        notes = NotesService(self.session)
        max_notes = max(1, min(int(max_files), MAX_IMPORT_NOTES))
        state = _ImportState()

        prepared: list[tuple[tuple[str, ...], str, bytes]] = []
        for uploaded in files:
            parts = self._safe_upload_parts(uploaded.relative_path)
            if parts is None:
                self._record_upload_skip(state, uploaded.relative_path)
                continue

            is_importable, _reason = self._is_text_bytes_importable(uploaded.content)
            if not is_importable:
                self._record_upload_skip(state, "/".join(parts))
                continue

            prepared.append((parts, uploaded.content.decode("utf-8"), uploaded.content))

        if not prepared:
            raise ValueError("No importable text files found in the selected upload")

        folder_cache: dict[tuple[str, ...], Any] = {}
        root_note: Any = None

        for parts, content, raw in sorted(prepared, key=lambda item: tuple(part.lower() for part in item[0])):
            parent_for_file = parent_id
            folder_parts = parts[:-1]
            skipped_for_limit = False

            for index, folder_name in enumerate(folder_parts):
                key = folder_parts[: index + 1]
                cached = folder_cache.get(key)
                if cached is not None:
                    parent_for_file = cached.id
                    continue

                if not self._can_import_more(state, max_notes=max_notes):
                    self._record_upload_skip(state, "/".join(parts))
                    skipped_for_limit = True
                    break

                folder_note = notes.create_note(
                    workspace_id=workspace_id,
                    parent_id=parent_for_file,
                    title=folder_name,
                    icon="📁",
                    content_markdown=f"Imported from browser upload path `{('/'.join(key))}`.\n",
                    content_json={
                        "source": {
                            "kind": "browser_upload",
                            "entry_type": "directory",
                            "path": "/".join(key),
                        }
                    },
                    user_id=user_id,
                )
                state.imported_count += 1
                folder_cache[key] = folder_note
                parent_for_file = folder_note.id
                if root_note is None:
                    root_note = folder_note

            if skipped_for_limit:
                continue

            if not self._can_import_more(state, max_notes=max_notes):
                self._record_upload_skip(state, "/".join(parts))
                continue

            file_note = notes.create_note(
                workspace_id=workspace_id,
                parent_id=parent_for_file,
                title=parts[-1],
                icon="📄",
                content_markdown=content,
                content_json={
                    "source": {
                        "kind": "browser_upload",
                        "entry_type": "file",
                        "path": "/".join(parts),
                        "size_bytes": len(raw),
                    }
                },
                user_id=user_id,
            )
            state.imported_count += 1
            if root_note is None:
                root_note = file_note

        if root_note is None:
            raise ValueError("The selected upload cannot be imported into notes")

        return FilesystemImportResult(
            source_path=self._upload_source_path([parts for parts, _content, _raw in prepared]),
            root_note_id=str(root_note.id),
            imported_count=state.imported_count,
            skipped_count=len(state.skipped_paths or []),
            skipped_paths=list(state.skipped_paths or []),
        )

    def _resolve_path(self, raw_path: str | None) -> Path:
        candidate: Path
        raw = (raw_path or "").strip()
        if raw:
            candidate = Path(raw).expanduser()
            if not candidate.is_absolute():
                candidate = Path.home() / candidate
        else:
            candidate = Path(settings.mcp_filesystem_path).expanduser()

        try:
            resolved = candidate.resolve(strict=False)
        except Exception as exc:
            raise ValueError(f"Invalid path: {raw_path}") from exc

        if not _is_within_allowed_roots(resolved):
            raise FilesystemPathNotAllowedError(
                f"Path is outside the allowed local roots: {resolved}"
            )
        if not resolved.exists():
            raise FilesystemPathNotFoundError(f"Path not found: {resolved}")
        return resolved

    def _best_matching_root(self, path: Path) -> Path:
        for root in sorted(_allowed_roots(), key=lambda candidate: len(str(candidate)), reverse=True):
            if path == root or root in path.parents:
                return root
        return Path.home().resolve()

    def _iter_entries(self, directory: Path) -> list[Path]:
        entries = []
        for entry in directory.iterdir():
            if entry.name in SKIPPED_ENTRY_NAMES:
                continue
            entries.append(entry)
        return sorted(
            entries,
            key=lambda entry: (
                0 if entry.is_dir() else 1,
                entry.name.lower(),
            ),
        )

    def _entry_for_browse(self, entry: Path) -> FilesystemEntry:
        hidden = entry.name.startswith(".")

        if entry.is_symlink():
            return FilesystemEntry(
                name=entry.name,
                path=str(entry),
                kind="symlink",
                hidden=hidden,
                importable=False,
                reason="Symlinks are not imported",
            )

        if entry.is_dir():
            return FilesystemEntry(
                name=entry.name,
                path=str(entry),
                kind="directory",
                hidden=hidden,
                importable=True,
            )

        if entry.is_file():
            is_importable, reason = self._is_text_file_importable(entry)
            return FilesystemEntry(
                name=entry.name,
                path=str(entry),
                kind="file",
                hidden=hidden,
                importable=is_importable,
                size_bytes=entry.stat().st_size,
                reason=reason,
            )

        return FilesystemEntry(
            name=entry.name,
            path=str(entry),
            kind="other",
            hidden=hidden,
            importable=False,
            reason="Unsupported filesystem entry",
        )

    def _is_text_bytes_importable(self, raw: bytes) -> tuple[bool, str | None]:
        if len(raw) > MAX_IMPORT_FILE_BYTES:
            return False, f"File exceeds {MAX_IMPORT_FILE_BYTES // 1024} KB"

        if b"\x00" in raw:
            return False, "Binary file"

        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            return False, "Non UTF-8 text"

        return True, None

    def _is_text_file_importable(self, path: Path) -> tuple[bool, str | None]:
        try:
            size_bytes = path.stat().st_size
        except OSError:
            return False, "Unable to inspect file"

        if size_bytes > MAX_IMPORT_FILE_BYTES:
            return False, f"File exceeds {MAX_IMPORT_FILE_BYTES // 1024} KB"

        try:
            with path.open("rb") as handle:
                raw = handle.read(MAX_IMPORT_FILE_BYTES + 1)
        except OSError:
            return False, "Unable to read file"

        return self._is_text_bytes_importable(raw)

    def _safe_upload_parts(self, relative_path: str) -> tuple[str, ...] | None:
        normalized = relative_path.replace("\\", "/").strip()
        if not normalized:
            return None

        path = PurePosixPath(normalized)
        if path.is_absolute():
            return None

        parts = tuple(part for part in path.parts if part not in {"", "."})
        if not parts or any(part == ".." for part in parts):
            return None
        return parts

    def _record_upload_skip(self, state: _ImportState, relative_path: str) -> None:
        assert state.skipped_paths is not None
        state.skipped_paths.append(relative_path)

    def _upload_source_path(self, paths: list[tuple[str, ...]]) -> str:
        if not paths:
            return "browser upload"
        first = paths[0][0]
        if all(len(path) > 1 and path[0] == first for path in paths):
            return first
        return "browser upload"

    def _has_importable_text_descendant(self, path: Path) -> bool:
        try:
            children = self._iter_entries(path)
        except OSError:
            return False

        for child in children:
            if child.is_symlink():
                continue
            if child.is_file() and self._is_text_file_importable(child)[0]:
                return True
            if child.is_dir() and child.name not in SKIPPED_RECURSIVE_DIRS:
                if self._has_importable_text_descendant(child):
                    return True
        return False

    def _can_import_more(self, state: _ImportState, *, max_notes: int) -> bool:
        return state.imported_count < max_notes

    def _record_skip(self, state: _ImportState, path: Path) -> None:
        assert state.skipped_paths is not None
        state.skipped_paths.append(str(path))

    def _import_directory(
        self,
        path: Path,
        *,
        notes: NotesService,
        workspace_id: str | uuid.UUID,
        parent_id: str | uuid.UUID | None,
        user_id: int | None,
        state: _ImportState,
        max_notes: int,
    ):
        if not self._can_import_more(state, max_notes=max_notes):
            raise ValueError("Import limit reached before creating the root note")

        content_markdown = f"Imported from `{path}`.\n"
        row = notes.create_note(
            workspace_id=workspace_id,
            parent_id=parent_id,
            title=path.name or str(path),
            icon="📁",
            content_markdown=content_markdown,
            content_json={
                "source": {
                    "kind": "filesystem",
                    "entry_type": "directory",
                    "path": str(path),
                }
            },
            user_id=user_id,
        )
        state.imported_count += 1

        try:
            children = self._iter_entries(path)
        except OSError:
            self._record_skip(state, path)
            return row

        for child in children:
            if not self._can_import_more(state, max_notes=max_notes):
                self._record_skip(state, child)
                continue

            if child.is_symlink():
                self._record_skip(state, child)
                continue

            if child.is_dir():
                if child.name in SKIPPED_RECURSIVE_DIRS:
                    self._record_skip(state, child)
                    continue
                if not self._has_importable_text_descendant(child):
                    self._record_skip(state, child)
                    continue
                self._import_directory(
                    child,
                    notes=notes,
                    workspace_id=workspace_id,
                    parent_id=row.id,
                    user_id=user_id,
                    state=state,
                    max_notes=max_notes,
                )
                continue

            if child.is_file():
                self._import_file(
                    child,
                    notes=notes,
                    workspace_id=workspace_id,
                    parent_id=row.id,
                    user_id=user_id,
                    state=state,
                    max_notes=max_notes,
                )
                continue

            self._record_skip(state, child)

        return row

    def _import_file(
        self,
        path: Path,
        *,
        notes: NotesService,
        workspace_id: str | uuid.UUID,
        parent_id: str | uuid.UUID | None,
        user_id: int | None,
        state: _ImportState,
        max_notes: int,
    ):
        if not self._can_import_more(state, max_notes=max_notes):
            self._record_skip(state, path)
            return None

        is_importable, _reason = self._is_text_file_importable(path)
        if not is_importable:
            self._record_skip(state, path)
            return None

        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            self._record_skip(state, path)
            return None

        try:
            size_bytes = path.stat().st_size
        except OSError:
            size_bytes = None

        row = notes.create_note(
            workspace_id=workspace_id,
            parent_id=parent_id,
            title=path.name,
            icon="📄",
            content_markdown=content,
            content_json={
                "source": {
                    "kind": "filesystem",
                    "entry_type": "file",
                    "path": str(path),
                    "size_bytes": size_bytes,
                }
            },
            user_id=user_id,
        )
        state.imported_count += 1
        return row


__all__ = [
    "FilesystemBrowseResult",
    "FilesystemEntry",
    "FilesystemImportResult",
    "FilesystemPathNotAllowedError",
    "FilesystemPathNotFoundError",
    "NotesFilesystemService",
    "UploadedFilesystemFile",
]
