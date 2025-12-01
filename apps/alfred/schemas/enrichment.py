from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class EnrichmentResult(BaseModel):
    """Canonical enrichment payload for documents and MindPalace pages.

    This is a versioned, stable shape intended to be forward/backward
    compatible across prompt/model changes.
    """

    summary_short: str = Field(..., description="One-paragraph summary (short).")
    summary_long: Optional[str] = Field(
        default=None, description="Extended summary or abstract (optional)."
    )
    highlights: List[str] = Field(
        default_factory=list,
        description="Key highlights or takeaways (keep concise).",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Short snake_case labels (prefer 2–6).",
    )
    topic_category: Optional[str] = Field(
        default=None, description="Primary topic/category as short slug."
    )
    topic_graph: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional topic relationships graph."
    )
    domain_summary: Optional[str] = Field(
        default=None, description="Optional domain-specific summary."
    )
    prompt_version: str = Field(
        default="v1", description="Prompt/spec version identifier (e.g., 'v1')."
    )
    model_name: str = Field(default="unknown", description="LLM model identifier.")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the enrichment was generated.",
    )

    @field_validator("summary_short")
    @classmethod
    def _trim_summary_short(cls, v: str) -> str:
        return (v or "").strip()

    @field_validator("summary_long", "domain_summary")
    @classmethod
    def _trim_optional_str(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if isinstance(v, str) else v

    @field_validator("highlights")
    @classmethod
    def _clean_highlights(cls, vals: List[str]) -> List[str]:
        cleaned: List[str] = []
        seen: set[str] = set()
        for item in vals or []:
            if not isinstance(item, str):
                continue
            s = item.strip()
            if not s or s.lower() in seen:
                continue
            cleaned.append(s)
            seen.add(s.lower())
        # Do not strictly enforce limit here; normalization helper will cap.
        return cleaned

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, vals: List[str]) -> List[str]:
        out: List[str] = []
        seen: set[str] = set()
        for t in vals or []:
            if not isinstance(t, str):
                continue
            s = t.strip().lower()
            # Convert to snake_case-ish slug
            slug_chars = []
            prev_us = False
            for ch in s:
                if ch.isalnum():
                    slug_chars.append(ch)
                    prev_us = False
                else:
                    if not prev_us:
                        slug_chars.append("_")
                        prev_us = True
            slug = "".join(slug_chars).strip("_")
            if not slug:
                continue
            if slug in seen:
                continue
            out.append(slug)
            seen.add(slug)
        # Keep at most 6 tags for consistency
        return out[:6]

    @field_validator("topic_category")
    @classmethod
    def _normalize_topic_category(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip().lower()
        slug_chars = []
        prev_us = False
        for ch in s:
            if ch.isalnum():
                slug_chars.append(ch)
                prev_us = False
            else:
                if not prev_us:
                    slug_chars.append("_")
                    prev_us = True
        slug = "".join(slug_chars).strip("_")
        return slug[:40] if slug else None


__all__ = ["EnrichmentResult"]
