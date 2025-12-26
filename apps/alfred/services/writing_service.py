from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from alfred.schemas.writing import WritingPreset, WritingRequest
from alfred.services.writer_graph_service import write as _write_graph
from alfred.services.writer_graph_service import write_stream as _write_stream_graph
from alfred.services.writing_presets import list_writing_presets, resolve_preset


@dataclass(frozen=True)
class WritingResult:
    preset_used: WritingPreset
    output: str


def write(req: WritingRequest) -> WritingResult:
    preset, output = _write_graph(req)
    return WritingResult(preset_used=preset, output=output)


def write_stream(req: WritingRequest) -> tuple[WritingPreset, Iterable[str]]:
    return _write_stream_graph(req)


__all__ = [
    "WritingResult",
    "list_writing_presets",
    "resolve_preset",
    "write",
    "write_stream",
]
