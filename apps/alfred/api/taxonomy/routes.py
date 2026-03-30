"""Taxonomy API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from alfred.core.dependencies import get_extraction_service
from alfred.schemas.taxonomy import (
    CreateTaxonomyNodeRequest,
    DeleteTaxonomyNodeResponse,
    TaxonomyNodeResponse,
    TaxonomyTreeNode,
    UpdateTaxonomyNodeRequest,
)
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
def reclassify_all() -> dict[str, str]:
    """Dispatch async batch reclassification via Celery.

    Returns a task_id that can be polled via GET /api/tasks/{task_id}.
    """
    from alfred.core.celery_client import get_celery_client

    celery_client = get_celery_client()
    async_result = celery_client.send_task(
        "alfred.tasks.taxonomy_reclassify.reclassify_all",
    )
    logger.info("Dispatched reclassify-all task: %s", async_result.id)
    return {"task_id": async_result.id, "status": "started"}


@router.post("/nodes", response_model=TaxonomyNodeResponse)
def create_node(
    req: CreateTaxonomyNodeRequest,
    svc: TaxonomyService = Depends(_get_taxonomy_service),
) -> TaxonomyNodeResponse:
    """Create a new taxonomy node.

    Args:
        req: Node name, level, optional parent_slug and description.

    Returns:
        The created taxonomy node.
    """
    try:
        node = svc.create_node(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TaxonomyNodeResponse(
        id=node.id,
        slug=node.slug,
        display_name=node.display_name,
        level=node.level,
        parent_slug=node.parent_slug,
        description=node.description,
        sort_order=node.sort_order,
    )


@router.patch("/nodes/{slug}", response_model=TaxonomyNodeResponse)
def update_node(
    slug: str,
    req: UpdateTaxonomyNodeRequest,
    svc: TaxonomyService = Depends(_get_taxonomy_service),
) -> TaxonomyNodeResponse:
    """Update an existing taxonomy node (rename, move parent, update description).

    Args:
        slug: Current slug of the node to update.
        req: Fields to update (name, parent_slug, description).

    Returns:
        The updated taxonomy node.
    """
    try:
        node = svc.update_node(slug, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TaxonomyNodeResponse(
        id=node.id,
        slug=node.slug,
        display_name=node.display_name,
        level=node.level,
        parent_slug=node.parent_slug,
        description=node.description,
        sort_order=node.sort_order,
    )


@router.delete("/nodes/{slug}", response_model=DeleteTaxonomyNodeResponse)
def delete_node(
    slug: str,
    reassign_parent: str | None = Query(
        None, description="Parent slug to reassign children to"
    ),
    svc: TaxonomyService = Depends(_get_taxonomy_service),
) -> DeleteTaxonomyNodeResponse:
    """Delete a taxonomy node.

    Args:
        slug: Slug of the node to delete.
        reassign_parent: Optional parent slug to reassign children to.

    Returns:
        Deletion result with count of reassigned children.
    """
    try:
        result = svc.delete_node(slug, reassign_parent=reassign_parent)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DeleteTaxonomyNodeResponse(
        deleted_slug=result["deleted_slug"],
        children_reassigned=result["children_reassigned"],
    )
