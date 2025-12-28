from __future__ import annotations

from collections.abc import Iterable

from alfred.schemas.writing import WritingPreset, WritingRequest
from alfred.services.writing_service import write as _write
from alfred.services.writing_service import write_stream as _write_stream


def write(req: WritingRequest) -> tuple[WritingPreset, str]:
    """
    Back-compat wrapper. Prefer `alfred.services.writing_service.write`.
    """
    result = _write(req)
    return result.preset_used, result.output


def write_stream(req: WritingRequest) -> tuple[WritingPreset, Iterable[str]]:
    """
    Back-compat wrapper. Prefer `alfred.services.writing_service.write_stream`.
    """
    return _write_stream(req)


__all__ = ["write", "write_stream"]
