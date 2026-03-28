# Taxonomy Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Wire the existing classify_taxonomy() into Alfred's enrichment pipeline so every document gets a structured 4-level classification (Domain, Subdomain, Microtopic, Topic) backed by a taxonomy_nodes registry table.

**Architecture:** Add a taxonomy_nodes table for canonical domain/subdomain/microtopic definitions. Add a classification JSONB column to documents. Create a TaxonomyService that calls the existing ExtractionService.classify_taxonomy(), normalizes the output to registry slugs, and persists the result. Wire into the enrichment pipeline. Batch re-classify existing documents.

**Tech Stack:** FastAPI, SQLModel, Alembic, PostgreSQL (JSONB), OpenAI gpt-4o-mini (via existing classify_taxonomy())

**Spec:** docs/superpowers/specs/2026-03-28-taxonomy-framework-design.md

---

## File Structure

**New files:**
- `apps/alfred/models/taxonomy.py` -- TaxonomyNodeRow model
- `apps/alfred/schemas/taxonomy.py` -- Pydantic schemas + slug normalization
- `apps/alfred/services/taxonomy_service.py` -- Classification + registry + tree queries
- `apps/alfred/api/taxonomy/__init__.py` -- Router export
- `apps/alfred/api/taxonomy/routes.py` -- API endpoints
- `apps/alfred/migrations/versions/d4e5f6a7b8c9_add_taxonomy_framework.py` -- Migration
- `tests/alfred/services/test_taxonomy_service.py` -- Unit tests
- `web/lib/api/types/taxonomy.ts` -- Frontend types
- `web/lib/api/taxonomy.ts` -- Frontend API client
- `web/features/taxonomy/queries.ts` -- React-query hooks

**Modified files:**
- `apps/alfred/models/__init__.py` -- Add TaxonomyNodeRow export
- `apps/alfred/models/doc_storage.py` -- Add classification column to DocumentRow
- `apps/alfred/services/doc_storage/_enrichment_mixin.py` -- Wire classify into enrichment
- `apps/alfred/tasks/document_enrichment.py` -- Zettel bridge uses classification
- `apps/alfred/services/doc_storage/utils.py` -- best_effort_primary_topic prefers classification
- `apps/alfred/api/__init__.py` -- Register taxonomy router
- `web/lib/api/routes.ts` -- Add taxonomy routes
- `web/app/(app)/dashboard/_components/coverage-card.tsx` -- Use domain display names

---

## Task 1: Taxonomy Node Model + Migration

**Files:**
- Create: `apps/alfred/models/taxonomy.py`
- Create: `apps/alfred/migrations/versions/d4e5f6a7b8c9_add_taxonomy_framework.py`
- Modify: `apps/alfred/models/__init__.py`
- Modify: `apps/alfred/models/doc_storage.py`

- [ ] Step 1: Create `apps/alfred/models/taxonomy.py` with TaxonomyNodeRow (SQLModel, table=True). Fields: id (auto PK), slug (String 128, unique), display_name (String 256), level (SmallInteger, 1=domain/2=subdomain/3=microtopic), parent_slug (FK to taxonomy_nodes.slug, nullable), description (Text nullable), sort_order (Integer default 0), created_at, updated_at. Indexes on level and parent_slug. Follow the same patterns as models/company.py (use sa.Column, utcnow, etc).

- [ ] Step 2: Create Alembic migration `d4e5f6a7b8c9_add_taxonomy_framework.py` (down_revision = "c3d4e5f6a7b8"). Three operations: (1) create taxonomy_nodes table with all columns and indexes, (2) bulk_insert 11 seed domains (system-design, ai-engineering, finance, startups, investments, writing-literature, politics-geopolitics, philosophy, movies-pop-culture, productivity-career, general) with sort_order 1-10 and 99 for general, (3) add classification JSONB column to documents table (nullable) with a btree index on classification->>'domain'.

- [ ] Step 3: Add `from alfred.models.taxonomy import TaxonomyNodeRow` and "TaxonomyNodeRow" to __all__ in `apps/alfred/models/__init__.py`.

- [ ] Step 4: Add `classification: dict[str, Any] | None` field to DocumentRow in `apps/alfred/models/doc_storage.py` (sa.Column(sa.JSON, nullable=True), default=None). Place it after the existing `enrichment` field.

- [ ] Step 5: Run migration: `cd /Users/ashwinrachha/coding/alfred && .venv/bin/python -m alembic upgrade head`. Verify 11 seed domains exist with a quick SELECT query.

- [ ] Step 6: Commit: "feat(taxonomy): add taxonomy_nodes table + classification column on documents"

---

## Task 2: Taxonomy Schemas + Slug Normalization

**Files:**
- Create: `apps/alfred/schemas/taxonomy.py`

- [ ] Step 1: Create `apps/alfred/schemas/taxonomy.py` with: `to_slug(raw: str) -> str` (lowercase, replace spaces/underscores with hyphens, strip non-alphanumeric except hyphens, collapse multiple hyphens, cap at 128 chars), `to_display_name(slug: str) -> str` (slug to Title Case), `TaxonomyRef(BaseModel)` with slug + display fields, `Classification(BaseModel)` with domain (TaxonomyRef), subdomain (TaxonomyRef), microtopics (list of TaxonomyRef), topic (dict with title + confidence), classified_at, classifier_version. Also `TaxonomyNodeResponse` and `TaxonomyTreeNode` (with children list for recursive tree).

- [ ] Step 2: Commit: "feat(taxonomy): add taxonomy Pydantic schemas + slug normalization"

---

## Task 3: TaxonomyService

**Files:**
- Create: `apps/alfred/services/taxonomy_service.py`
- Create: `tests/alfred/services/test_taxonomy_service.py`

- [ ] Step 1: Write tests in `tests/alfred/services/test_taxonomy_service.py`. Test to_slug with inputs: "Machine Learning" -> "machine-learning", "machine_learning" -> "machine-learning", "AI/ML & Data" -> "ai-ml-data", 200-char input caps at 128. Test to_display_name: "machine-learning" -> "Machine Learning". Test uppercase domain mapping: "AI" -> "ai", "SYSTEM_DESIGN" -> "system-design", "MOVIES_POP_CULTURE" -> "movies-pop-culture".

- [ ] Step 2: Run tests to verify they pass (pure function tests, no DB needed).

- [ ] Step 3: Create `apps/alfred/services/taxonomy_service.py` with class TaxonomyService. Constructor takes optional extraction_service. Methods: (1) classify_and_register(text) -- calls extraction_service.classify_taxonomy(), maps uppercase domain output to slugs via DOMAIN_SLUG_MAP dict (AI->ai-engineering, SYSTEM_DESIGN->system-design, etc), ensures taxonomy nodes exist via _ensure_node(), returns Classification or None on failure. (2) _ensure_node(slug, level, parent_slug) -- get-or-create a TaxonomyNodeRow. (3) get_domains() -- SELECT level=1 ORDER BY sort_order. (4) get_tree(domain_slug?) -- builds nested TaxonomyTreeNode list from flat DB rows. (5) reclassify_all() -- iterates all documents, calls classify_and_register on each, stores result in doc.classification, returns stats dict.

- [ ] Step 4: Run ruff check on new files.

- [ ] Step 5: Commit: "feat(taxonomy): TaxonomyService with classify, registry, tree queries, batch reclassify"

---

## Task 4: Wire into Enrichment Pipeline

**Files:**
- Modify: `apps/alfred/services/doc_storage/_enrichment_mixin.py` (after extract_all call, ~line 97)
- Modify: `apps/alfred/tasks/document_enrichment.py` (_create_zettel_from_enrichment, ~line 36-48)
- Modify: `apps/alfred/services/doc_storage/utils.py` (best_effort_primary_topic, ~line 155)

- [ ] Step 1: In _enrichment_mixin.py, after the extract_all() call and before enrichment result processing, add a try/except block that creates TaxonomyService(extraction_service=self.extraction_service), calls classify_and_register(cleaned_text), and stores the result as classification_payload. Then add classification_payload to the updates dict if not None. Wrap in try/except so enrichment never fails due to classification.

- [ ] Step 2: In document_enrichment.py _create_zettel_from_enrichment(), after extracting topics, check doc.get("classification") for domain/subdomain. If present, use domain slug as zettel topic and build tags from domain + subdomain + microtopic slugs. Fall back to old primary_topic if no classification.

- [ ] Step 3: In utils.py best_effort_primary_topic(), add an optional classification parameter. Check classification.domain.display first before falling back to existing topics logic. Update callers to pass classification where available.

- [ ] Step 4: Run full test suite to verify nothing broke.

- [ ] Step 5: Commit: "feat(taxonomy): wire classify_taxonomy into enrichment pipeline + zettel bridge"

---

## Task 5: API Endpoints

**Files:**
- Create: `apps/alfred/api/taxonomy/__init__.py`
- Create: `apps/alfred/api/taxonomy/routes.py`
- Modify: `apps/alfred/api/__init__.py`

- [ ] Step 1: Create `apps/alfred/api/taxonomy/__init__.py` exporting router. Create `apps/alfred/api/taxonomy/routes.py` with APIRouter(prefix="/api/taxonomy", tags=["taxonomy"]). Three endpoints: GET /domains (list all level-1 nodes), GET /tree (full tree with optional domain filter query param), POST /reclassify-all (batch reclassification, returns stats).

- [ ] Step 2: Register taxonomy_router in `apps/alfred/api/__init__.py`.

- [ ] Step 3: Run ruff check on new files.

- [ ] Step 4: Commit: "feat(taxonomy): add /api/taxonomy endpoints (domains, tree, reclassify-all)"

---

## Task 6: Batch Reclassify Existing Documents

- [ ] Step 1: Run the batch reclassification script via Python: import get_extraction_service from dependencies, create TaxonomyService, call reclassify_all(), print stats.

- [ ] Step 2: Verify results by querying documents with non-null classification and printing domain/subdomain for each. Also query taxonomy_nodes to see what subdomains/microtopics were auto-created.

---

## Task 7: Frontend Types + API Client + Queries

**Files:**
- Create: `web/lib/api/types/taxonomy.ts`
- Create: `web/lib/api/taxonomy.ts`
- Create: `web/features/taxonomy/queries.ts`
- Modify: `web/lib/api/routes.ts`

- [ ] Step 1: Create `web/lib/api/types/taxonomy.ts` with TaxonomyNode (id, slug, display_name, level, parent_slug, description, sort_order) and TaxonomyTreeNode (slug, display_name, level, doc_count, children array recursive).

- [ ] Step 2: Create `web/lib/api/taxonomy.ts` with listTaxonomyDomains(), getTaxonomyTree(domain?), reclassifyAll() using apiFetch.

- [ ] Step 3: Create `web/features/taxonomy/queries.ts` with useTaxonomyDomains() and useTaxonomyTree(domain?) react-query hooks (staleTime 5 min).

- [ ] Step 4: Add taxonomy routes to `web/lib/api/routes.ts`: domains, tree, reclassifyAll.

- [ ] Step 5: Commit: "feat(taxonomy): frontend types, API client, and react-query hooks"

---

## Task 8: Update Dashboard Coverage Widget

**Files:**
- Modify: `web/app/(app)/dashboard/_components/coverage-card.tsx`

- [ ] Step 1: Read coverage-card.tsx. Update the topicCounts useMemo to prefer classification.domain.display over primary_topic. Add classification to the ExplorerDocumentItem type if needed. Ensure the backend serializes the classification field in the explorer response.

- [ ] Step 2: Build check to verify frontend compiles.

- [ ] Step 3: Commit: "feat(taxonomy): dashboard coverage widget uses taxonomy domains"

---

## Task 9: Final Verification

- [ ] Step 1: Run backend tests (uv run pytest).
- [ ] Step 2: Run ruff check on all backend code.
- [ ] Step 3: Run frontend build check.
- [ ] Step 4: API smoke test: GET /api/taxonomy/domains, GET /api/taxonomy/tree.
- [ ] Step 5: Push to remote.
