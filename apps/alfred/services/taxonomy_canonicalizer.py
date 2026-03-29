"""Smart taxonomy canonicalization service.

Provides fuzzy matching and synonym resolution to prevent duplicate taxonomy nodes.
"""

from difflib import SequenceMatcher
from typing import Optional


# Hardcoded synonym map: maps various terms to their canonical slugs
_SYNONYM_MAP = {
    "artificial-intelligence": "ai-engineering",
    "ai": "ai-engineering",
    "machine-learning": "ai-engineering",
    "ml": "ai-engineering",
    "deep-learning": "ai-engineering",
    "distributed-systems": "system-design",
    "microservices": "system-design",
    "investing": "finance",
    "investments": "finance",
    "stocks": "finance",
    "crypto": "finance",
    "stoicism": "philosophy",
    "ethics": "philosophy",
    "existentialism": "philosophy",
    "geopolitics": "politics",
    "international-relations": "politics",
}


def _normalize_slug(slug: str) -> str:
    """Normalize a slug: lowercase, underscores to hyphens."""
    return slug.lower().replace("_", "-")


def _strip_plural(slug: str) -> str:
    """Strip common plural suffix if present."""
    if slug.endswith("s") and len(slug) > 2:
        return slug[:-1]
    return slug


def _fuzzy_similarity(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, a, b).ratio()


def find_canonical_match(slug: str, existing_slugs: list[str]) -> Optional[str]:
    """Find canonical match for a slug among existing slugs.

    Priority order:
    1. Exact match (normalized: lowercase, underscores→hyphens)
    2. Synonym map lookup
    3. Plural/singular normalization
    4. Fuzzy matching (threshold ≥0.8)

    Args:
        slug: The slug to find a match for
        existing_slugs: List of existing taxonomy node slugs at the same level

    Returns:
        The matching existing slug, or None if no match found
    """
    if not existing_slugs:
        return None

    normalized_input = _normalize_slug(slug)

    # 1. Exact match (normalized)
    for existing in existing_slugs:
        if _normalize_slug(existing) == normalized_input:
            return existing

    # 2. Synonym map lookup
    if normalized_input in _SYNONYM_MAP:
        canonical = _SYNONYM_MAP[normalized_input]
        # Check if the canonical term exists in the existing slugs
        for existing in existing_slugs:
            if _normalize_slug(existing) == canonical:
                return existing

    # 3. Plural/singular normalization
    stripped_input = _strip_plural(normalized_input)
    for existing in existing_slugs:
        normalized_existing = _normalize_slug(existing)
        # Try both directions: input plural → existing singular, or input singular → existing plural
        if stripped_input == normalized_existing or normalized_input == _strip_plural(normalized_existing):
            return existing

    # 4. Fuzzy matching (threshold ≥0.8)
    best_match = None
    best_score = 0.0
    threshold = 0.8

    for existing in existing_slugs:
        normalized_existing = _normalize_slug(existing)
        score = _fuzzy_similarity(normalized_input, normalized_existing)
        if score >= threshold and score > best_score:
            best_score = score
            best_match = existing

    return best_match
