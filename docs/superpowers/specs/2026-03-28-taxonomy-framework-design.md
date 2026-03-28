# Taxonomy Framework — Standardized Knowledge Classification

**Date:** 2026-03-28
**Status:** Approved
**Branch:** `alfred-revamp` (target: main)

## Problem

Alfred auto-generates document topics via LLM extraction, producing freeform snake_case labels like `focus_music`, `celery_task_testing`, `python_json_serialization`, `cosmology`, `legal_trial` — all at the same level with no hierarchy. The dashboard "Coverage" widget shows these as a flat, inconsistent list. There's no relationship between document topics, learning topics, and zettelkasten card topics. The knowledge hub feels like a dump of auto-categorized noise rather than an organized knowledge system.

## Key Insight

The codebase already has `ExtractionService.classify_taxonomy()` — a 4-level hierarchical classifier (Domain → Subdomain → Microtopics → Topic) with 10 curriculum domains matching the user's interests. **It's just not wired into the enrichment pipeline.** The infrastructure exists; it's disconnected.

## Design Decisions

1. **11 top-level domains:** 10 curriculum domains + "General" catch-all
2. **Naming:** Dual-field — `slug` (lowercase-hyphen, for matching) + `display_name` (Title Case, for UI)
3. **Depth:** 4 levels (Domain → Subdomain → Microtopic → Topic) using the existing `classify_taxonomy()` output
4. **Growth:** Domains are fixed (seed data). Subdomains and microtopics auto-create from LLM classification output
5. **Migration:** Batch re-classify all existing documents
6. **Backwards compat:** Old `topics` and `tags` fields stay. New `classification` field is the source of truth

## 1. Taxonomy Registry Table

New table: `taxonomy_nodes`

```sql
CREATE TABLE taxonomy_nodes (
    id          SERIAL PRIMARY KEY,
    slug        VARCHAR(128) NOT NULL UNIQUE,
    display_name VARCHAR(256) NOT NULL,
    level       SMALLINT NOT NULL,  -- 1=domain, 2=subdomain, 3=microtopic
    parent_slug VARCHAR(128) REFERENCES taxonomy_nodes(slug) ON DELETE SET NULL,
    description TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMP NOT NULL DEFAULT now(),
    updated_at  TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_taxonomy_nodes_level ON taxonomy_nodes(level);
CREATE INDEX idx_taxonomy_nodes_parent ON taxonomy_nodes(parent_slug);
```

### Seed Data (11 Domains)

| slug | display_name | level | sort_order |
|------|-------------|-------|------------|
| `system-design` | System Design | 1 | 1 |
| `ai-engineering` | AI Engineering | 1 | 2 |
| `finance` | Finance | 1 | 3 |
| `startups` | Startups | 1 | 4 |
| `investments` | Investments | 1 | 5 |
| `writing-literature` | Writing & Literature | 1 | 6 |
| `politics-geopolitics` | Politics & Geopolitics | 1 | 7 |
| `philosophy` | Philosophy | 1 | 8 |
| `movies-pop-culture` | Movies & Pop Culture | 1 | 9 |
| `productivity-career` | Productivity & Career | 1 | 10 |
| `general` | General | 1 | 99 |

Subdomains and microtopics are auto-created as `classify_taxonomy()` returns new values. The service normalizes the LLM output to a slug, checks if the node exists, and creates it if not.

### Slug Normalization Rules

Input → lowercase → replace spaces/underscores with hyphens → strip non-alphanumeric (except hyphens) → collapse multiple hyphens → trim → cap at 128 chars.

Examples:
- `"Machine Learning"` → `"machine-learning"`
- `"machine_learning"` → `"machine-learning"`
- `"LSM Trees"` → `"lsm-trees"`
- `"AI/ML"` → `"ai-ml"`

## 2. Document Classification Column

Add `classification` JSONB column to `documents` table (nullable).

```json
{
  "domain": {"slug": "system-design", "display": "System Design"},
  "subdomain": {"slug": "databases", "display": "Databases"},
  "microtopics": [
    {"slug": "lsm-trees", "display": "LSM Trees"},
    {"slug": "write-ahead-log", "display": "Write-Ahead Log"}
  ],
  "topic": {
    "title": "LSM Tree Compaction Strategies",
    "confidence": 0.92
  },
  "classified_at": "2026-03-28T20:00:00Z",
  "classifier_version": "v1"
}
```

### Field Semantics

| Field | Type | Description |
|-------|------|-------------|
| `domain` | `{slug, display}` | Top-level curriculum domain (always present) |
| `subdomain` | `{slug, display}` | Second-level category (always present, may be "general" within a domain) |
| `microtopics` | `[{slug, display}]` | 0-5 specific sub-sub-topics |
| `topic` | `{title, confidence}` | LLM's best description of the document's specific topic + confidence score |
| `classified_at` | ISO datetime | When classification was performed |
| `classifier_version` | string | Version identifier for classification prompt/model (enables re-classification when prompt improves) |

### Backwards Compatibility

- `DocumentRow.topics` (old field with `{"primary": str, "secondary": list}`) stays. Not removed.
- `DocumentRow.tags` (old field with free-form list) stays.
- `best_effort_primary_topic()` utility gains a new first-try: check `classification.domain.display` before falling back to `topics.primary`.
- Frontend reads from `classification` when available, falls back to `topics` for unclassified documents.

## 3. TaxonomyService

New service: `apps/alfred/services/taxonomy_service.py`

### Methods

```python
class TaxonomyService:
    def classify_and_register(
        self, text: str, *, doc_id: str | None = None
    ) -> Classification:
        """
        1. Call ExtractionService.classify_taxonomy(text)
        2. Normalize LLM output to slugs
        3. Lookup/create taxonomy_nodes for domain, subdomain, microtopics
        4. Return structured Classification object
        """

    def resolve_slug(self, raw_name: str) -> TaxonomyNode | None:
        """Normalize any input to the canonical taxonomy node."""

    def get_tree(self, domain_slug: str | None = None) -> list[TreeNode]:
        """Return the full taxonomy tree or a subtree for UI rendering."""

    def get_domains(self) -> list[TaxonomyNode]:
        """Return all level-1 domains, sorted by sort_order."""

    def reclassify_document(self, doc_id: str) -> Classification:
        """Re-run classification for a single document."""

    def reclassify_all(self, *, batch_size: int = 10) -> dict:
        """Batch re-classify all documents. Returns stats."""
```

### Integration with Enrichment Pipeline

In `DocStorageService.enrich_document()` (or the enrichment mixin), after `extract_all()`:

```python
# Existing: extract topics, tags, entities
enrichment = extraction_service.extract_all(text, ...)

# NEW: classify into taxonomy
taxonomy_service = TaxonomyService(session=session)
classification = taxonomy_service.classify_and_register(text, doc_id=doc_id)

# Store classification
document.classification = classification.model_dump()
```

This adds one LLM call (~$0.02 with gpt-4o-mini, ~3s latency) per enrichment run. If `classify_taxonomy()` fails (LLM timeout, malformed output), the enrichment still succeeds — classification is best-effort. The document gets `classification: null` and falls back to the old `topics` field for display.

## 4. Zettelkasten Bridge Update

When `_create_zettel_from_enrichment()` creates a zettel card from a classified document:

```python
# Current: zettel.topic = document.topics["primary"]  (e.g., "focus_music")
# New: zettel.topic = classification["domain"]["slug"]  (e.g., "system-design")
# New: zettel.tags = [subdomain.slug] + [mt.slug for mt in microtopics]
```

This means zettel cards inherit the structured taxonomy instead of garbage freeform topics.

## 5. API Endpoints

New endpoints under `/api/taxonomy/`:

```
GET  /api/taxonomy/domains              → list all domains with counts
GET  /api/taxonomy/tree                 → full tree (domains + subdomains + microtopics)
GET  /api/taxonomy/tree/{domain_slug}   → subtree for one domain
POST /api/taxonomy/reclassify-all       → trigger batch reclassification (admin)
```

Existing endpoints updated:
- `GET /api/documents/explorer` — add `filter_domain` query param (filters by `classification.domain.slug`)
- Dashboard "Coverage" widget — read from `classification.domain` instead of `topics.primary`

## 6. Frontend Changes

### Dashboard Coverage Widget
- Group by domain instead of flat topic list
- Show: domain name, document count, subdomain breakdown on hover/expand
- Replace snake_case labels with display_names

### Document Explorer
- Add domain filter dropdown (11 options)
- Show domain badge on each document card
- Breadcrumb: Domain > Subdomain > Topic

### Knowledge Hub
- Tree navigation in the left panel: collapsible Domain → Subdomain → Microtopic
- Click a node to filter documents/zettels to that taxonomy branch

## 7. Migration Plan

### Database

1. Create `taxonomy_nodes` table with seed data (11 domains)
2. Add `classification` column to `documents` (nullable JSONB)
3. Add GIN index on `classification` for JSONB queries

### Data

4. Run `TaxonomyService.reclassify_all()` as a one-time batch job
5. This calls `classify_taxonomy()` for each document, stores the result, and auto-creates taxonomy nodes

### Estimated Cost

~10 documents × $0.02/doc = $0.20 total for the batch reclassification.

## Out of Scope (v1)

- Synonym/alias table (e.g., "ML" → "machine-learning")
- User-defined domains (the 11 are fixed for v1)
- Cross-domain classification (one document = one domain)
- Taxonomy versioning/history
- Embedding-based classifier (optimization for v2 if LLM costs become a concern)

## Dependencies

- `ExtractionService.classify_taxonomy()` — already exists, just needs wiring
- `prompts/classification/taxonomy_min.txt` — already exists with domain definitions
- OpenAI API (gpt-4o-mini) — for classification LLM calls
- Existing enrichment pipeline — integration point
