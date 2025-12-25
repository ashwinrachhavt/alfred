from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class EnrichmentResult(BaseModel):
    """Canonical enrichment payload for documents and MindPalace pages.

    This is a versioned, stable shape intended to stay consistent across
    prompt/model changes.
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


def normalize_enrichment(data: dict | EnrichmentResult | None) -> EnrichmentResult:
    """
    Normalize various enrichment shapes into EnrichmentResult.

    Accepts either a dict with keys like `summary`, `topics`, `tags`, `insights`,
    or an already-validated EnrichmentResult. Missing fields are filled with
    reasonable defaults.
    """
    if isinstance(data, EnrichmentResult):
        return data

    data = data or {}

    # Defaults
    summary_short = None
    summary_long = None
    highlights: list[str] = []
    tags: list[str] = []
    topic_category = None
    topic_graph = None

    # 1) Enrichment-like direct keys
    if isinstance(data.get("summary_short"), str):
        summary_short = data.get("summary_short")
    if isinstance(data.get("summary_long"), str):
        summary_long = data.get("summary_long")
    if isinstance(data.get("highlights"), list):
        highlights = [str(x) for x in data.get("highlights") or []]
    if isinstance(data.get("tags"), list):
        tags = [str(x) for x in data.get("tags") or []]
    if isinstance(data.get("topic_category"), str):
        topic_category = data.get("topic_category")
    if isinstance(data.get("topic_graph"), dict):
        topic_graph = data.get("topic_graph")

    # 2) Map from alternative shapes (summary/topics/insights)
    if not summary_short:
        summary = data.get("summary") or {}
        if isinstance(summary, dict):
            summary_short = summary.get("short") or summary.get("summary") or summary.get("brief")
            summary_long = summary_long or summary.get("detailed") or summary.get("long")
        elif isinstance(summary, str):
            summary_short = summary

    if not highlights:
        # try bullets, key_points, insights
        bullets = data.get("bullets") or data.get("key_points") or data.get("insights")
        if isinstance(bullets, list):
            highlights = [str(x) for x in bullets if isinstance(x, str)]

    if not tags:
        if isinstance(data.get("tags"), list):
            tags = [str(x) for x in data.get("tags") if isinstance(x, str)]

    topics = data.get("topics")
    if isinstance(topics, dict):
        topic_category = topic_category or topics.get("primary") or topics.get("category")
        # carry over additional topics if present
        secondary = topics.get("secondary")
        if isinstance(secondary, list) and not tags:
            tags = [str(x) for x in secondary if isinstance(x, str)]

    # Build result (validators normalize/cap fields)
    return EnrichmentResult(
        summary_short=summary_short or "",
        summary_long=summary_long,
        highlights=highlights,
        tags=tags,
        topic_category=topic_category,
        topic_graph=topic_graph,
    )


__all__ = ["EnrichmentResult", "normalize_enrichment"]
