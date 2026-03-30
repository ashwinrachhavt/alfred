"""Taxonomy classification and management service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func
from sqlmodel import select

from alfred.core.database import SessionLocal
from alfred.models.doc_storage import DocumentRow
from alfred.models.taxonomy import TaxonomyNodeRow
from alfred.models.zettel import ZettelCard
from alfred.schemas.taxonomy import (
    Classification,
    CreateTaxonomyNodeRequest,
    TaxonomyRef,
    TaxonomyTreeNode,
    UpdateTaxonomyNodeRequest,
    to_display_name,
    to_slug,
)
from alfred.services.taxonomy_canonicalizer import find_canonical_match

logger = logging.getLogger(__name__)

# Map extraction service uppercase domains to canonical slugs
DOMAIN_SLUG_MAP = {
    "AI": "ai-engineering",
    "SYSTEM_DESIGN": "system-design",
    "FINANCE": "finance",
    "STARTUPS": "startups",
    "INVESTING": "investments",
    "WRITING": "writing-literature",
    "POLITICS": "politics-geopolitics",
    "MOVIES_POP_CULTURE": "movies-pop-culture",
    "PHILOSOPHY": "philosophy",
    "PRODUCTIVITY_CAREER": "productivity-career",
}


class TaxonomyService:
    """Service for taxonomy classification and tree management."""

    def __init__(self, extraction_service=None) -> None:
        """Initialize taxonomy service.

        Args:
            extraction_service: Optional extraction service for classify_taxonomy().
                If None, classification methods will raise an error.
        """
        self._extraction_service = extraction_service

    def classify_and_register(self, text: str) -> Classification | None:
        """Classify text and ensure taxonomy nodes exist in DB.

        Calls extraction_service.classify_taxonomy(), maps uppercase domains
        to slugs, ensures nodes exist, and returns a Classification object.

        Args:
            text: Text to classify

        Returns:
            Classification object or None if extraction fails
        """
        if self._extraction_service is None:
            raise RuntimeError("ExtractionService required for classification")

        try:
            # Call extraction service
            result = self._extraction_service.classify_taxonomy(text=text)

            # Extract raw values
            raw_domain = result.get("domain")
            raw_subdomain = result.get("subdomain")
            raw_microtopics = result.get("microtopics") or []
            topic_dict = result.get("topic")

            # Map domain slug (uppercase domains → canonical slugs)
            domain_slug = None
            if raw_domain:
                domain_slug = DOMAIN_SLUG_MAP.get(raw_domain.upper(), to_slug(raw_domain))

            # Ensure domain node exists
            domain_ref = None
            if domain_slug:
                domain_node = self._ensure_node(slug=domain_slug, level=1)
                domain_ref = TaxonomyRef(
                    slug=domain_node.slug,
                    display_name=domain_node.display_name,
                )

            # Ensure subdomain node exists
            subdomain_ref = None
            if raw_subdomain and domain_slug:
                subdomain_slug = to_slug(raw_subdomain)
                subdomain_node = self._ensure_node(
                    slug=subdomain_slug,
                    level=2,
                    parent_slug=domain_slug,
                )
                subdomain_ref = TaxonomyRef(
                    slug=subdomain_node.slug,
                    display_name=subdomain_node.display_name,
                )

            # Ensure microtopic nodes exist
            microtopic_refs: list[TaxonomyRef] = []
            parent_slug = subdomain_ref.slug if subdomain_ref else domain_slug
            if parent_slug:
                for raw_micro in raw_microtopics:
                    micro_slug = to_slug(raw_micro)
                    if micro_slug:
                        micro_node = self._ensure_node(
                            slug=micro_slug,
                            level=3,
                            parent_slug=parent_slug,
                        )
                        microtopic_refs.append(
                            TaxonomyRef(
                                slug=micro_node.slug,
                                display_name=micro_node.display_name,
                            )
                        )

            # Build classification result
            classification = Classification(
                domain=domain_ref,
                subdomain=subdomain_ref,
                microtopics=microtopic_refs,
                topic=topic_dict,
                classified_at=datetime.now(UTC).isoformat(),
                classifier_version="v1",
            )

            return classification

        except Exception as exc:
            logger.warning("Classification failed: %s", exc, exc_info=True)
            return None

    def _ensure_node(
        self,
        slug: str,
        level: int,
        parent_slug: str | None = None,
    ) -> TaxonomyNodeRow:
        """Get or create a taxonomy node.

        Uses smart canonicalization to prevent duplicates. Before creating a new node,
        checks for exact matches, synonyms, plural/singular variants, and fuzzy matches
        among existing nodes at the same level.

        Args:
            slug: Node slug (normalized)
            level: Hierarchy level (1-3)
            parent_slug: Parent node slug (required for level > 1)

        Returns:
            TaxonomyNodeRow instance (existing or newly created)
        """
        with SessionLocal() as session:
            # Try to get existing node by exact slug
            node = session.exec(
                select(TaxonomyNodeRow).where(TaxonomyNodeRow.slug == slug)
            ).first()

            if node is not None:
                return node

            # Try canonical matching before creating new node
            # Get all existing slugs at the same level
            existing_nodes = session.exec(
                select(TaxonomyNodeRow).where(TaxonomyNodeRow.level == level)
            ).all()
            existing_slugs = [n.slug for n in existing_nodes]

            canonical = find_canonical_match(slug, existing_slugs)
            if canonical:
                # Found a canonical match, return the existing node
                canonical_node = session.exec(
                    select(TaxonomyNodeRow).where(TaxonomyNodeRow.slug == canonical)
                ).first()
                if canonical_node:
                    logger.info(
                        "Canonicalized '%s' to existing node '%s' (level %s)",
                        slug,
                        canonical,
                        level,
                    )
                    return canonical_node

            # No match found, create new node
            node = TaxonomyNodeRow(
                slug=slug,
                display_name=to_display_name(slug),
                level=level,
                parent_slug=parent_slug,
                sort_order=0,
            )
            session.add(node)
            session.commit()
            session.refresh(node)
            logger.info("Created taxonomy node: %s (level %s)", slug, level)

            return node

    def get_domains(self) -> list[TaxonomyNodeRow]:
        """Get all level-1 (domain) nodes sorted by sort_order.

        Returns:
            List of domain TaxonomyNodeRow instances
        """
        with SessionLocal() as session:
            nodes = session.exec(
                select(TaxonomyNodeRow)
                .where(TaxonomyNodeRow.level == 1)
                .order_by(TaxonomyNodeRow.sort_order, TaxonomyNodeRow.slug)
            ).all()
            return list(nodes)

    def get_tree(self, domain_slug: str | None = None) -> list[TaxonomyTreeNode]:
        """Build nested tree from flat DB rows.

        Args:
            domain_slug: Optional domain slug to filter by. If None, returns all domains.

        Returns:
            List of TaxonomyTreeNode instances with nested children
        """
        with SessionLocal() as session:
            # Fetch all relevant nodes
            stmt = select(TaxonomyNodeRow).order_by(
                TaxonomyNodeRow.level,
                TaxonomyNodeRow.sort_order,
                TaxonomyNodeRow.slug,
            )

            if domain_slug:
                # Filter: domain itself + all descendants
                # We need domain node + all nodes where parent chain includes domain_slug
                nodes = []
                domain_node = session.exec(
                    select(TaxonomyNodeRow).where(TaxonomyNodeRow.slug == domain_slug)
                ).first()
                if domain_node:
                    nodes.append(domain_node)
                    # Get all level-2 children
                    level2_nodes = session.exec(
                        select(TaxonomyNodeRow)
                        .where(TaxonomyNodeRow.parent_slug == domain_slug)
                        .order_by(TaxonomyNodeRow.sort_order, TaxonomyNodeRow.slug)
                    ).all()
                    nodes.extend(level2_nodes)
                    # Get all level-3 children
                    for l2_node in level2_nodes:
                        level3_nodes = session.exec(
                            select(TaxonomyNodeRow)
                            .where(TaxonomyNodeRow.parent_slug == l2_node.slug)
                            .order_by(TaxonomyNodeRow.sort_order, TaxonomyNodeRow.slug)
                        ).all()
                        nodes.extend(level3_nodes)
            else:
                nodes = session.exec(stmt).all()

            # Build tree with real counts
            zettel_counts = self._count_zettels_per_node()
            return self._build_tree(list(nodes), zettel_counts)

    def _build_tree(
        self,
        nodes: list[TaxonomyNodeRow],
        zettel_counts: dict[str, int] | None = None,
    ) -> list[TaxonomyTreeNode]:
        """Build nested tree structure from flat list of nodes.

        Args:
            nodes: Flat list of TaxonomyNodeRow instances
            zettel_counts: Optional map of slug -> zettel count

        Returns:
            List of root-level TaxonomyTreeNode instances with nested children
        """
        counts = zettel_counts or {}

        # Create lookup map
        node_map: dict[str, TaxonomyTreeNode] = {}
        for node in nodes:
            node_map[node.slug] = TaxonomyTreeNode(
                slug=node.slug,
                display_name=node.display_name,
                level=node.level,
                doc_count=counts.get(node.slug, 0),
                children=[],
            )

        # Build parent-child relationships
        root_nodes: list[TaxonomyTreeNode] = []
        for node in nodes:
            tree_node = node_map[node.slug]
            if node.parent_slug and node.parent_slug in node_map:
                parent = node_map[node.parent_slug]
                parent.children.append(tree_node)
            else:
                root_nodes.append(tree_node)

        # Roll up child counts to parents
        def _rollup(tree_node: TaxonomyTreeNode) -> int:
            child_total = sum(_rollup(c) for c in tree_node.children)
            tree_node.doc_count += child_total
            return tree_node.doc_count

        for root in root_nodes:
            _rollup(root)

        return root_nodes

    def create_node(self, req: CreateTaxonomyNodeRequest) -> TaxonomyNodeRow:
        """Create a new taxonomy node.

        Args:
            req: CreateTaxonomyNodeRequest with name, level, optional parent_slug.

        Returns:
            The created TaxonomyNodeRow.

        Raises:
            ValueError: If slug already exists or parent not found.
        """
        slug = to_slug(req.name)
        if not slug:
            raise ValueError("Name produces an empty slug")

        with SessionLocal() as session:
            existing = session.exec(
                select(TaxonomyNodeRow).where(TaxonomyNodeRow.slug == slug)
            ).first()
            if existing:
                raise ValueError(f"Taxonomy node with slug '{slug}' already exists")

            if req.parent_slug:
                parent = session.exec(
                    select(TaxonomyNodeRow).where(TaxonomyNodeRow.slug == req.parent_slug)
                ).first()
                if parent is None:
                    raise ValueError(f"Parent node '{req.parent_slug}' not found")

            node = TaxonomyNodeRow(
                slug=slug,
                display_name=req.name.strip(),
                level=req.level,
                parent_slug=req.parent_slug,
                description=req.description,
                sort_order=0,
            )
            session.add(node)
            session.commit()
            session.refresh(node)
            logger.info("Created taxonomy node: %s (level %s)", slug, req.level)
            return node

    def update_node(self, slug: str, req: UpdateTaxonomyNodeRequest) -> TaxonomyNodeRow:
        """Update an existing taxonomy node (rename, move parent, update description).

        Args:
            slug: Current slug of the node to update.
            req: UpdateTaxonomyNodeRequest with optional new name, parent_slug, description.

        Returns:
            The updated TaxonomyNodeRow.

        Raises:
            ValueError: If node not found, or new slug conflicts.
        """
        with SessionLocal() as session:
            node = session.exec(
                select(TaxonomyNodeRow).where(TaxonomyNodeRow.slug == slug)
            ).first()
            if node is None:
                raise ValueError(f"Taxonomy node '{slug}' not found")

            if req.name is not None:
                new_slug = to_slug(req.name)
                if new_slug != slug:
                    conflict = session.exec(
                        select(TaxonomyNodeRow).where(TaxonomyNodeRow.slug == new_slug)
                    ).first()
                    if conflict:
                        raise ValueError(f"Slug '{new_slug}' already taken")
                    # Update children that reference old slug
                    children = session.exec(
                        select(TaxonomyNodeRow).where(TaxonomyNodeRow.parent_slug == slug)
                    ).all()
                    for child in children:
                        child.parent_slug = new_slug
                        session.add(child)
                    node.slug = new_slug
                node.display_name = req.name.strip()

            if req.parent_slug is not None:
                if req.parent_slug:
                    parent = session.exec(
                        select(TaxonomyNodeRow).where(
                            TaxonomyNodeRow.slug == req.parent_slug
                        )
                    ).first()
                    if parent is None:
                        raise ValueError(f"Parent node '{req.parent_slug}' not found")
                node.parent_slug = req.parent_slug or None

            if req.description is not None:
                node.description = req.description

            node.updated_at = datetime.now(UTC)
            session.add(node)
            session.commit()
            session.refresh(node)
            logger.info("Updated taxonomy node: %s", node.slug)
            return node

    def delete_node(self, slug: str, reassign_parent: str | None = None) -> dict:
        """Delete a taxonomy node and optionally reassign its children.

        Args:
            slug: Slug of the node to delete.
            reassign_parent: If provided, reassign children to this parent slug.
                If None, children are deleted via CASCADE.

        Returns:
            Dict with deleted_slug and children_reassigned count.

        Raises:
            ValueError: If node not found.
        """
        with SessionLocal() as session:
            node = session.exec(
                select(TaxonomyNodeRow).where(TaxonomyNodeRow.slug == slug)
            ).first()
            if node is None:
                raise ValueError(f"Taxonomy node '{slug}' not found")

            children = session.exec(
                select(TaxonomyNodeRow).where(TaxonomyNodeRow.parent_slug == slug)
            ).all()
            children_count = len(children)

            if reassign_parent and children:
                for child in children:
                    child.parent_slug = reassign_parent
                    session.add(child)

            session.delete(node)
            session.commit()
            logger.info(
                "Deleted taxonomy node: %s (children reassigned: %d)",
                slug,
                children_count,
            )
            return {"deleted_slug": slug, "children_reassigned": children_count}

    def _propagate_classification_to_zettels(
        self,
        session,
        doc_id: str,
        classification: Classification,
    ) -> int:
        """Update all zettels linked to a document with its taxonomy classification.

        Returns number of zettels updated.
        """
        zettels = session.exec(
            select(ZettelCard).where(ZettelCard.document_id == doc_id)
        ).all()

        if not zettels:
            return 0

        domain = classification.domain
        subdomain = classification.subdomain

        new_topic = domain.slug if domain else None
        new_tags = [t for t in [
            domain.slug if domain else None,
            subdomain.slug if subdomain else None,
            *[mt.slug for mt in (classification.microtopics or [])[:3]],
        ] if t]

        count = 0
        for zettel in zettels:
            existing_tags = set(zettel.tags or [])
            zettel.topic = new_topic
            zettel.tags = list(set(new_tags) | existing_tags)
            session.add(zettel)
            count += 1

        return count

    def _classify_standalone_zettels(self, batch_size: int = 10) -> int:
        """Classify zettels that have no document_id using their own content."""
        classified_count = 0

        with SessionLocal() as session:
            offset = 0
            while True:
                batch = session.exec(
                    select(ZettelCard)
                    .where(
                        (ZettelCard.document_id.is_(None))
                        | (ZettelCard.document_id == "")
                    )
                    .where(ZettelCard.status == "active")
                    .offset(offset)
                    .limit(batch_size)
                ).all()

                if not batch:
                    break

                for zettel in batch:
                    try:
                        parts = [zettel.title or ""]
                        if zettel.content:
                            parts.append(zettel.content)
                        if zettel.summary:
                            parts.append(zettel.summary)
                        text = " ".join(p.strip() for p in parts if p and p.strip())

                        if not text.strip():
                            continue

                        classification = self.classify_and_register(text)
                        if classification:
                            domain = classification.domain
                            subdomain = classification.subdomain

                            new_topic = domain.slug if domain else None
                            new_tags = [t for t in [
                                domain.slug if domain else None,
                                subdomain.slug if subdomain else None,
                                *[mt.slug for mt in (classification.microtopics or [])[:3]],
                            ] if t]

                            existing_tags = set(zettel.tags or [])
                            zettel.topic = new_topic
                            zettel.tags = list(set(new_tags) | existing_tags)
                            session.add(zettel)
                            classified_count += 1

                    except Exception as exc:
                        logger.warning(
                            "Failed to classify standalone zettel %s: %s",
                            zettel.id, exc,
                        )

                session.commit()
                offset += batch_size

        return classified_count

    def reclassify_all(self, batch_size: int = 10) -> dict[str, int]:
        """Iterate all documents, classify each, store result, and propagate to zettels.

        Also classifies standalone zettels (no document_id) directly.

        Returns:
            Stats dict with counts: total, classified, failed, skipped,
            zettels_updated, standalone_classified
        """
        if self._extraction_service is None:
            raise RuntimeError("ExtractionService required for reclassification")

        stats = {
            "total": 0,
            "classified": 0,
            "failed": 0,
            "skipped": 0,
            "zettels_updated": 0,
            "standalone_classified": 0,
        }

        with SessionLocal() as session:
            total = session.exec(select(DocumentRow)).all()
            stats["total"] = len(total)

            offset = 0
            while True:
                batch = session.exec(
                    select(DocumentRow).offset(offset).limit(batch_size)
                ).all()

                if not batch:
                    break

                for doc in batch:
                    try:
                        text = doc.cleaned_text or ""
                        if not text.strip() and doc.summary:
                            if isinstance(doc.summary, dict):
                                text = doc.summary.get("text", "") or doc.summary.get("summary", "")

                        if not text.strip():
                            stats["skipped"] += 1
                            continue

                        classification = self.classify_and_register(text)
                        if classification:
                            doc.classification = classification.model_dump()
                            session.add(doc)
                            stats["classified"] += 1

                            # Propagate to linked zettels
                            updated = self._propagate_classification_to_zettels(
                                session, doc.id, classification,
                            )
                            stats["zettels_updated"] += updated
                        else:
                            stats["failed"] += 1

                    except Exception as exc:
                        logger.warning("Failed to classify doc %s: %s", doc.id, exc)
                        stats["failed"] += 1

                session.commit()
                offset += batch_size

        # Phase 2: classify standalone zettels (no document_id)
        stats["standalone_classified"] = self._classify_standalone_zettels(batch_size)

        logger.info("Reclassification complete: %s", stats)
        return stats

    def _count_zettels_per_node(self) -> dict[str, int]:
        """Count zettels associated with each taxonomy node slug.

        Counts by matching zettel.topic (domain) and zettel.tags (subdomain/microtopics).
        """
        counts: dict[str, int] = {}

        with SessionLocal() as session:
            # Count by topic (domain-level)
            topic_counts = session.exec(
                select(ZettelCard.topic, func.count(ZettelCard.id))
                .where(ZettelCard.topic.isnot(None))
                .where(ZettelCard.status == "active")
                .group_by(ZettelCard.topic)
            ).all()
            for topic_slug, count in topic_counts:
                if topic_slug:
                    counts[topic_slug] = count

            # Count by tags (subdomain/microtopic level) — scan active zettels
            zettels = session.exec(
                select(ZettelCard)
                .where(ZettelCard.status == "active")
                .where(ZettelCard.tags.isnot(None))
            ).all()
            for zettel in zettels:
                for tag in (zettel.tags or []):
                    # Skip domain-level tags (already counted above via topic)
                    if tag and tag != zettel.topic:
                        counts[tag] = counts.get(tag, 0) + 1

        return counts


__all__ = ["TaxonomyService", "DOMAIN_SLUG_MAP"]
