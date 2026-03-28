"""Taxonomy API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from alfred.core.dependencies import get_extraction_service
from alfred.schemas.taxonomy import TaxonomyNodeResponse, TaxonomyTreeNode
from alfred.services.taxonomy_service import TaxonomyService

router = APIRouter(prefix="/api/taxonomy", tags=["taxonomy"])
logger = logging.getLogger(__name__)


def _get_taxonomy_service(
    extraction=Depends(get_extraction_service),
) -> TaxonomyService:
    """Dependency injection for TaxonomyService."""
    return TaxonomyService(extraction_service=extraction)


@router.get("/domains", response_model=list[TaxonomyNodeResponse])
def get_domains(
    svc: TaxonomyService = Depends(_get_taxonomy_service),
) -> list[TaxonomyNodeResponse]:
    """Get all domain (level-1) taxonomy nodes.

    Returns:
        List of domain taxonomy nodes sorted by sort_order
    """
    domains = svc.get_domains()
    return [
        TaxonomyNodeResponse(
            id=d.id,
            slug=d.slug,
            display_name=d.display_name,
            level=d.level,
            parent_slug=d.parent_slug,
            description=d.description,
            sort_order=d.sort_order,
        )
        for d in domains
    ]


@router.get("/tree", response_model=list[TaxonomyTreeNode])
def get_tree(
    domain: str | None = Query(None, description="Optional domain slug to filter by"),
    svc: TaxonomyService = Depends(_get_taxonomy_service),
) -> list[TaxonomyTreeNode]:
    """Get taxonomy tree hierarchy.

    Args:
        domain: Optional domain slug to filter by. If provided, returns only
            that domain and its descendants. If None, returns all domains.

    Returns:
        List of root-level taxonomy tree nodes with nested children
    """
    return svc.get_tree(domain_slug=domain)


@router.post("/reclassify-all")
def reclassify_all(
    svc: TaxonomyService = Depends(_get_taxonomy_service),
) -> dict[str, int]:
    """Batch reclassify all documents using the taxonomy classifier.

    This endpoint will:
    1. Iterate through all documents in the database
    2. Classify each document using the extraction service
    3. Store the classification result in the document's classification field
    4. Ensure all taxonomy nodes exist in the database

    Returns:
        Stats dict with counts: total, classified, failed, skipped
    """
    logger.info("Starting batch reclassification of all documents")
    stats = svc.reclassify_all()
    logger.info("Batch reclassification complete: %s", stats)
    return stats
