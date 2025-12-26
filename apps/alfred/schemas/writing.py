from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

WritingIntent = Literal["compose", "rewrite", "reply", "edit"]


class WritingPreset(BaseModel):
    """A site-specific writing style preset."""

    key: str = Field(..., description="Stable preset identifier (e.g. 'linkedin', 'x').")
    title: str = Field(..., description="Human-friendly preset name.")
    description: str = Field("", description="What this preset optimizes for.")
    max_chars: Optional[int] = Field(
        default=None,
        description="If set, enforce a hard character budget for the final output.",
    )
    format: Literal["plain", "markdown"] = Field(
        default="plain",
        description="Preferred output formatting for the target surface.",
    )


class WritingRequest(BaseModel):
    """Non-streaming writing request for browser extensions/clients."""

    intent: WritingIntent = Field(default="rewrite")
    site_url: str = Field("", description="Current site URL (used to select a preset).")
    preset: Optional[str] = Field(
        default=None,
        description="Optional preset key override (e.g. 'linkedin'); if omitted, inferred from site_url.",
    )
    instruction: str = Field(
        "",
        description="What you want Alfred to do (e.g. 'Make this clearer and more confident').",
    )
    draft: str = Field("", description="User's current text/draft.")
    selection: str = Field("", description="Highlighted text (if any).")
    page_title: str = Field("", description="Current page title (optional).")
    page_text: str = Field(
        "",
        description="Optional page context (should be short; do not paste full pages).",
    )
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Optional sampling temperature override.",
    )
    max_chars: Optional[int] = Field(
        default=None,
        ge=1,
        le=10000,
        description="Optional character limit override (takes precedence over preset max_chars).",
    )


class WritingResponse(BaseModel):
    """Non-streaming writing response."""

    preset_used: WritingPreset
    output: str


__all__ = [
    "WritingIntent",
    "WritingPreset",
    "WritingRequest",
    "WritingResponse",
]
