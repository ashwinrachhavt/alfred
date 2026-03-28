"""Taxonomy classification schemas and utilities."""

from __future__ import annotations

import re

from pydantic import BaseModel


def to_slug(raw: str) -> str:
    """Convert raw string to normalized taxonomy slug.

    Rules:
    - Lowercase
    - Replace spaces and underscores with hyphens
    - Strip non-alphanumeric except hyphens
    - Collapse multiple hyphens
    - Cap at 128 characters

    Examples:
        "Machine Learning" -> "machine-learning"
        "machine_learning" -> "machine-learning"
        "AI/ML & Data" -> "ai-ml-data"
        "AI" -> "ai"
        "SYSTEM_DESIGN" -> "system-design"
    """
    slug = raw.strip().lower()
    # Replace spaces and underscores with hyphens
    slug = slug.replace(" ", "-").replace("_", "-")
    # Replace other common separators with hyphens before stripping
    slug = re.sub(r"[/\\&+]", "-", slug)
    # Strip non-alphanumeric except hyphens
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    # Cap at 128 characters
    return slug[:128]


def to_display_name(slug: str) -> str:
    """Convert slug to Title Case display name.

    Examples:
        "machine-learning" -> "Machine Learning"
        "ai" -> "Ai"
    """
    return slug.replace("-", " ").title()


class TaxonomyRef(BaseModel):
    """Reference to a taxonomy node (slug + display name)."""

    slug: str
    display_name: str


class Classification(BaseModel):
    """Document classification result from extraction service.

    Maps to taxonomy hierarchy:
    - domain: Level 1 (e.g., "ai-engineering")
    - subdomain: Level 2 (e.g., "machine-learning")
    - microtopics: Level 3 list (e.g., ["transformers", "llms"])
    - topic: Freeform extracted topic with confidence
    """

    domain: TaxonomyRef | None = None
    subdomain: TaxonomyRef | None = None
    microtopics: list[TaxonomyRef] = []
    topic: dict | None = None  # {"title": str, "confidence": float}
    classified_at: str | None = None
    classifier_version: str = "v1"


class TaxonomyNodeResponse(BaseModel):
    """API response for a single taxonomy node."""

    id: int
    slug: str
    display_name: str
    level: int
    parent_slug: str | None = None
    description: str | None = None
    sort_order: int = 0


class TaxonomyTreeNode(BaseModel):
    """Nested tree representation of taxonomy hierarchy."""

    slug: str
    display_name: str
    level: int
    doc_count: int = 0
    children: list[TaxonomyTreeNode] = []


__all__ = [
    "to_slug",
    "to_display_name",
    "TaxonomyRef",
    "Classification",
    "TaxonomyNodeResponse",
    "TaxonomyTreeNode",
]
