from __future__ import annotations

from typing import TypedDict

from alfred.schemas.writing import WritingPreset, WritingRequest


class WriterState(TypedDict, total=False):
    req: WritingRequest
    preset: WritingPreset
    site_rules: str
    voice_examples: str
    cache_hit: bool
    output: str

