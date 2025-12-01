from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from alfred.schemas.enrichment import EnrichmentResult


def _coerce_dict(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        # Fallback: wrap under common key if it's a plain string
        return {"summary_short": raw}
    # Pydantic models or objects with dict-like API
    if hasattr(raw, "model_dump"):
        try:
            return raw.model_dump()  # type: ignore[attr-defined]
        except Exception:
            pass
    if hasattr(raw, "dict"):
        try:
            return raw.dict()  # type: ignore[attr-defined]
        except Exception:
            pass
    raise ValueError("normalize_enrichment expected a dict-like object or JSON string")


def _pick_first_str(
    obj: Dict[str, Any], keys: List[str], *, nested_keys: Optional[List[str]] = None
) -> Optional[str]:
    for k in keys:
        val = obj.get(k)
        if isinstance(val, str):
            s = val.strip()
            if s:
                return s
        if isinstance(val, dict):
            # allow nested 'summary': {'short': '...'}
            nk = nested_keys or ["short", "summary_short", "value"]
            nested = _pick_first_str(val, nk)  # type: ignore[arg-type]
            if nested:
                return nested
    return None


def _pick_first_list(obj: Dict[str, Any], keys: List[str]) -> List[str]:
    for k in keys:
        val = obj.get(k)
        if isinstance(val, list):
            out: List[str] = []
            for item in val:
                if isinstance(item, str):
                    s = item.strip()
                    if s:
                        out.append(s)
            if out:
                return out
        if isinstance(val, str):
            # sometimes a newline-joined string sneaks in
            parts = [p.strip() for p in val.split("\n") if p.strip()]
            if parts:
                return parts
    return []


def normalize_enrichment(raw: Dict[str, Any] | Any) -> EnrichmentResult:
    """Normalize messy LLM JSON into a canonical EnrichmentResult.

    - Fills defaults for missing fields
    - Trims whitespace
    - Limits highlights to top 5
    - Drops unknown/extra keys
    - Enforces tags/topic_category constraints
    """

    obj = _coerce_dict(raw)

    # Extract core fields with reasonable fallbacks
    summary_short = _pick_first_str(
        obj,
        [
            "summary_short",
            "summary",
            "short",
            "abstract",
            "overview",
        ],
        nested_keys=["short", "summary_short", "value"],
    )
    summary_long = (
        _pick_first_str(
            obj,
            ["summary_long", "summary", "long", "details"],
            nested_keys=["long", "summary_long", "value"],
        )
        or None
    )

    if not summary_short and summary_long:
        # fallback to first sentence or slice of long
        s = summary_long.strip()
        dot = s.find(".")
        summary_short = (s[: dot + 1] if dot != -1 else s)[:360]

    if not summary_short:
        raise ValueError("enrichment.summary_short is required")

    highlights = _pick_first_list(obj, ["highlights", "bullets", "key_points"]) or []
    # Cap and dedupe while preserving order
    seen_h: set[str] = set()
    cleaned_h: List[str] = []
    for h in highlights:
        k = h.lower()
        if k in seen_h:
            continue
        seen_h.add(k)
        cleaned_h.append(h)
        if len(cleaned_h) >= 5:
            break

    tags = _pick_first_list(obj, ["tags", "keywords"]) or []

    # Topic category derive
    raw_topic = _pick_first_str(obj, ["topic_category", "primary_topic", "topic", "category"])

    # Build preliminary structure and let EnrichmentResult validators normalize
    base: Dict[str, Any] = {
        "summary_short": summary_short[:360].strip(),
        "summary_long": (summary_long[:2000].strip() if summary_long else None),
        "highlights": cleaned_h,
        "tags": tags,
        "topic_category": raw_topic,
        "topic_graph": obj.get("topic_graph") if isinstance(obj.get("topic_graph"), dict) else None,
        "domain_summary": _pick_first_str(obj, ["domain_summary", "domain", "domain_notes"]),
        "prompt_version": (_pick_first_str(obj, ["prompt_version", "version"]) or "v1"),
        "model_name": _pick_first_str(obj, ["model_name", "model", "llm"]) or "unknown",
        "generated_at": _pick_first_str(obj, ["generated_at", "timestamp"]) or None,
    }

    # Parse/normalize timestamp
    gen_at = base["generated_at"]
    if isinstance(gen_at, str):
        try:
            # datetime.fromisoformat with Z suffix handling
            s = gen_at.replace("Z", "+00:00")
            base["generated_at"] = datetime.fromisoformat(s)
        except Exception:
            base["generated_at"] = datetime.now(timezone.utc)
    elif not isinstance(gen_at, datetime):
        base["generated_at"] = datetime.now(timezone.utc)

    # Create pydantic model (validators will slugify tags/topic)
    enriched = EnrichmentResult(**base)

    # Ensure topic_category exists; fall back to first tag or 'general'
    if not enriched.topic_category:
        topic = enriched.tags[0] if enriched.tags else "general"
        enriched.topic_category = topic if topic else "general"

    return enriched


__all__ = ["normalize_enrichment"]
