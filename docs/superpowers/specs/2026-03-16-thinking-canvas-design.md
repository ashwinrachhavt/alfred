# Thinking Canvas + Decomposition Engine

**Date:** 2026-03-16
**Status:** Approved
**Branch:** `knowledge` (target: `alfred-revamp`)

## Overview

A block-based thinking environment for Alfred where the user writes freely while AI surfaces relevant knowledge from their existing graph. Includes a structured decomposition engine that breaks any topic into governing laws, frameworks, canonical anchors, and predictions — producing modular blocks the user can rearrange, refine, and eventually publish as zettelkasten cards or learning topics.

**Core loop:** Input (URL/text/topic) → Structured decomposition → User refines + adds thinking → Rich zettelkasten card/synthesis note → Feeds back into knowledge base for future sessions.

**Identity:** Alfred is a knowledge factory. It ingests, decomposes, connects, and helps you think so you can capitalize on what you know.

## 1. Data Model

### ThinkingSession Table

New SQL table managed via Alembic migration.

```sql
CREATE TABLE thinking_sessions (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    title         VARCHAR(500),
    status        VARCHAR(20) NOT NULL DEFAULT 'draft',  -- draft | published | archived
    blocks        JSONB NOT NULL DEFAULT '[]'::jsonb,
    tags          JSONB DEFAULT '[]'::jsonb,
    topic         VARCHAR(500),
    source_input  JSONB,           -- what triggered decomposition (url, text, topic name)
    pinned        BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMP NOT NULL DEFAULT now(),
    updated_at    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_thinking_sessions_user ON thinking_sessions(user_id);
CREATE INDEX idx_thinking_sessions_status ON thinking_sessions(user_id, status);
CREATE INDEX idx_thinking_sessions_updated ON thinking_sessions(user_id, updated_at DESC);
```

**All queries filter by `user_id`** — sessions are scoped to the authenticated user. No cross-user data leakage.

### Block Schema

Each element in the `blocks` JSONB array:

```json
{
  "id": "uuid-v4",
  "type": "freeform | demolition | framework | anchor | law | prediction | connection | insight",
  "content": "markdown string",
  "meta": {
    "law_number": 3,
    "confidence": 0.8,
    "timeframe": "within 5 years",
    "source_card_id": 42,
    "source_doc_id": "doc_abc",
    "source_entity_id": 5,
    "validated_at": null,
    "collapsed": false
  },
  "order": 0
}
```

**Design decisions:**
- Blocks stored as JSON array inside the session row, not as separate DB rows. One query loads the full session.
- Block `type` maps to the five-layer decomposition method plus `freeform` (user's own writing), `connection` (surfaced link to existing knowledge), and `insight` (user's synthesis).
- Published sessions create zettelkasten cards from selected blocks.

### Block Meta Schemas (per type)

Each block type has required and optional meta fields:

| Block Type | Required Meta | Optional Meta |
|-----------|---------------|---------------|
| `freeform` | — | `collapsed` |
| `demolition` | — | `collapsed` |
| `framework` | — | `collapsed` |
| `anchor` | — | `source_doc_id`, `collapsed` |
| `law` | `law_number: int` | `collapsed` |
| `prediction` | `confidence: float` | `timeframe: str`, `validated_at: datetime`, `collapsed` |
| `connection` | At least one of: `source_card_id`, `source_doc_id`, `source_entity_id` | `collapsed` |
| `insight` | — | `collapsed` |

The `ThinkingSessionService` validates required meta fields on save. Missing required fields produce a 422 response.

### Block ID Generation

Block IDs are UUID v4 strings. **Frontend generates IDs** for user-created blocks (typing, slash commands). **Backend generates IDs** for decomposition-produced blocks. Both sides use standard UUID v4 — no coordination needed.

## 2. Decomposition Engine (Backend)

### Service: `DecompositionService`

Located at `apps/alfred/services/decomposition_service.py`.

**Input:** One of:
- Topic name (e.g., "information theory")
- URL (scraped via Firecrawl, then decomposed)
- Raw text (pasted paragraph, article, notes)

**Output:** Array of typed blocks.

### Pipeline

```
Input (topic/url/text)
  → [1] Normalize to text
        URL → scrape via Firecrawl (localhost:3002)
        Topic → web search (SearXNG) + existing KB search
        Text → use directly
  → [2] LLM structured output → 5-layer decomposition
  → [3] Knowledge graph query → find cross-domain connections
  → [4] Merge connections as additional blocks
  → [5] Return block array
```

### Pydantic Schemas

```python
class LawItem(BaseModel):
    name: str                # e.g., "The Law of Asymmetry"
    description: str         # 2-3 sentence explanation

class PredictionItem(BaseModel):
    claim: str
    confidence: float        # 0.0 - 1.0
    timeframe: str | None

class DecompositionOutput(BaseModel):
    demolition: str          # Layer 1: What assumption to challenge
    framework: str           # Layer 2: Theoretical lens to install
    anchor: str              # Layer 3: Canonical text/case study
    laws: list[LawItem]      # Layer 4: 3-5 named governing principles
    predictions: list[PredictionItem]  # Layer 5: Falsifiable claims
```

### Block Conversion (DecompositionOutput → blocks array)

The `DecompositionOutput` is converted to blocks in fixed order:

| Order | Source Field | Block Type | Notes |
|-------|-------------|------------|-------|
| 0 | `demolition` | `demolition` | Single block |
| 1 | `framework` | `framework` | Single block |
| 2 | `anchor` | `anchor` | Single block |
| 3..N | `laws[0..N]` | `law` | One block per law, `meta.law_number` = 1-indexed |
| N+1..M | `predictions[0..M]` | `prediction` | One block per prediction, `meta.confidence` from model |

After these, connection blocks from step [3] (knowledge graph query) are appended with `order` values continuing the sequence.

### Error Handling

| Failure | Behavior |
|---------|----------|
| Firecrawl down (URL input) | Return 502 with `{"error": "url_scrape_failed", "detail": "..."}` |
| SearXNG down (topic input) | Fall back to KB-only search; proceed with whatever text is available |
| LLM returns malformed output | Retry once; if still fails, return 500 with `{"error": "decomposition_failed"}` |
| Knowledge graph query fails | Return decomposition blocks without connection blocks + `"warnings": ["connection_search_unavailable"]` |

Partial success is preferred over total failure. If the LLM decomposition succeeds but connection-finding fails, return the decomposition blocks with a warnings array.

### Prompt

Located at `apps/alfred/prompts/decomposition/system.md`. Encodes the five-layer method as a general-purpose decomposition framework (not tied to any specific author's style).

### API

```
POST /api/thinking/decompose
{
  "input_type": "topic" | "url" | "text",
  "content": "information theory",
  "connect_to_existing": true
}
→ { "blocks": [...typed blocks...] }
```

## 3. Knowledge Surfacing

### Trigger

Debounced — frontend sends the last ~200 words of writing buffer every 5 seconds of idle time.

### Pipeline

```
Writing buffer text
  → [1] Generate embedding (reuse existing embedding infrastructure)
  → [2] Parallel search:
      ├── Zettel cards (vector similarity via Qdrant)
      ├── Learning entities (keyword match on entity names)
      └── Documents (vector similarity via Qdrant)
  → [3] Deduplicate & rank by relevance
  → [4] Filter out already-surfaced items for this session
  → [5] Return top N
```

### Ranking

The `ThinkingSessionService.surface()` method generates an **ad-hoc embedding** from the writing buffer text, then performs vector search against Qdrant and entity keyword matching directly. It does NOT call `ZettelkastenService.suggest_links()` (which requires an existing card_id). Instead, it reuses the same **composite scoring formula** from `_quality()` (semantic similarity + tag overlap + topic match) adapted to work with raw text input rather than an existing card.

### API

```
POST /api/thinking/surface
{
  "text": "...last 200 words...",
  "session_id": 42,
  "limit": 5
}
→ {
    "connections": [
      {
        "type": "zettel" | "entity" | "document",
        "id": ...,
        "title": "...",
        "snippet": "...",
        "relevance": 0.87
      }
    ]
  }
```

### User Interaction

Results appear in a right sidebar panel. User can:
- **Drag** a connection into the canvas → creates a `connection` block
- **Dismiss** → won't resurface for this session
- **Ignore** → fades after next batch

## 4. Frontend Architecture

### Routes

Uses the existing `(app)` layout group for consistent navigation shell.

```
/(app)/think                    → Session list (recent, pinned, archived)
/(app)/think/new                → Fresh canvas + optional decompose trigger
/(app)/think/[sessionId]        → Resume session
```

Decomposition can be triggered from within a session via the `/decompose` slash command (no query-param URL pattern needed).

### Layout

Two-panel split: editor (~70%) + surfacing sidebar (~30%, collapsible).

### Block Editor: BlockNote

Built on Tiptap/ProseMirror (same foundation as existing notes editor). Provides Notion-style block editing with drag handles, slash menus, and custom block types.

### Custom Block Types

| Block Type | Visual | Behavior |
|-----------|--------|----------|
| `freeform` | Default text, clean & minimal | Standard rich text editing |
| `demolition` | Red-orange left border, "Challenge" icon | Collapsible, italic prompt |
| `framework` | Blue left border, "Lens" icon | Collapsible |
| `anchor` | Purple left border, "Book" icon | Can link to KB document |
| `law` | Green left border, numbered badge | Auto-numbered within session |
| `prediction` | Amber left border, confidence meter | Editable confidence slider + timeframe |
| `connection` | Dashed gray border, link icon | Created from sidebar drag. Shows source + snippet. |
| `insight` | Gold left border, lightbulb icon | User's synthesis — the wisdom block |

### Slash Commands

| Command | Action |
|---------|--------|
| `/decompose` | Modal: paste URL/text/topic → run engine → insert blocks |
| `/law` | Insert empty law block |
| `/prediction` | Insert empty prediction block |
| `/insight` | Insert empty insight block |
| `/connect` | Inline KB search → insert connection block |
| `/surface` | Force-refresh surfacing sidebar |

### Publish Flow

`Cmd+Enter` or Publish button opens a sheet:
- Title (auto-suggested)
- Tags (auto-suggested + manual)
- Publish mode:
  - Single zettelkasten card (compressed)
  - Multiple cards (one per law/insight/prediction)
  - Learning topic + resources
- Creates cards/topics, links to session, marks session as "published"

### Tech Stack

- `@blocknote/react` — block editor core
- `@blocknote/shadcn` — theming (matches existing shadcn/ui)
- `react-query` — data fetching (already in use)
- `framer-motion` — sidebar transitions (already in use)

**BlockNote dependency note:** BlockNote is built on Tiptap/ProseMirror and will coexist with the existing raw Tiptap notes editor (`markdown-notes-editor.tsx`). Before implementation, verify that BlockNote's bundled Tiptap version is compatible with the existing `@tiptap/*@^3.15.3` packages to avoid duplicate/conflicting ProseMirror instances. If incompatible, pin both to the same Tiptap minor version. The two editors serve different purposes (notes = flat rich text; thinking = typed blocks) and do not share state.

## 5. Session Lifecycle & Autosave

### Autosave

3-second debounce after last edit. Sends `PATCH /api/thinking/sessions/{id}` with full blocks array. Optimistic updates — UI never blocks on save. Status indicator: "Saving..." / "Saved" / "Offline".

**Payload size limit:** 500KB max per PATCH request (enforced server-side). For v1, full-blocks-on-save is acceptable — a session with 50 blocks of ~2KB each is ~100KB. Differential sync is deferred to v2 if sessions grow significantly larger.

### Session States

```
draft → published → archived
         ↓
       (fork → new draft)
```

- **Draft** — Active, autosaves, top of list
- **Published** — Read-only, can fork into new draft. Cards/topics created.
- **Archived** — Soft-deleted, restorable

### Session List (`/think`)

Sorted by `updated_at` desc. Shows: title, timestamp, status badge, block summary (e.g., "3 laws, 2 predictions, 1 insight"), pin toggle.

### Complete API Surface

```
POST   /api/thinking/sessions              → Create session
GET    /api/thinking/sessions              → List (filterable by status, tags; paginated: limit + skip)
GET    /api/thinking/sessions/{id}         → Get with blocks
PATCH  /api/thinking/sessions/{id}         → Autosave (500KB max payload)
PATCH  /api/thinking/sessions/{id}/archive → Archive (soft delete)

POST   /api/thinking/decompose             → Run decomposition engine
POST   /api/thinking/surface               → Knowledge surfacing
POST   /api/thinking/sessions/{id}/publish → Publish to zettelkasten/learning
POST   /api/thinking/sessions/{id}/fork    → Fork into new draft
```

### Publish Sequence

```
POST /publish { mode: "multiple_cards", selected_block_ids: [...], tags: [...] }
  → Create zettel card per selected block (via ZettelkastenService)
  → Set zettel card metadata: thinking_session_id = session.id (for traceability)
  → Generate embeddings for each card
  → Link cards to each other (session = implicit link group via shared session_id)
  → If learning topic mode: create LearningTopic + LearningResources
  → Mark session status = "published"
  → Return { cards_created: N, topic_created: { id, name } | null }
```

**Traceability:** Each zettel card created from a session stores the `thinking_session_id` in its metadata JSON. This allows navigating from a card back to the session that produced it.

### State Transitions

Valid transitions (enforced server-side):
- `draft` → `published` (via publish endpoint)
- `draft` → `archived` (via archive endpoint)
- `published` → `archived` (via archive endpoint)
- `published` → `draft` (via fork endpoint — creates a **new** session in draft)
- `archived` → `draft` (via restore — `PATCH /sessions/{id}` with `status: "draft"`)

## Dependencies

### Backend (existing, reused)
- `LLMService.structured()` — Pydantic-validated LLM outputs
- `ZettelkastenService` — card creation, link suggestions, composite scoring
- `LearningService` — topic/resource creation, entity graph
- `ExtractionService` — entity/relation extraction
- `DocStorageService` — document text retrieval
- Firecrawl (localhost:3002) — URL scraping
- SearXNG (localhost:8080) — web search for topic decomposition
- Qdrant — vector similarity search

### Backend (new)
- `DecompositionService` — five-layer decomposition pipeline
- `ThinkingSessionService` — CRUD + publish + fork + surfacing
- Alembic migration for `thinking_sessions` table
- Prompt template: `prompts/decomposition/system.md`

### Frontend (existing, reused)
- shadcn/ui component library
- react-query data fetching
- Framer Motion animations
- Clerk auth

### Frontend (new)
- `@blocknote/react` + `@blocknote/shadcn`
- Custom block type renderers (8 types)
- `/think` route with session list + editor + sidebar
- Publish sheet component

## Out of Scope (for v1)

- Real-time collaboration / multiplayer
- Mobile-optimized layout
- Browser extension integration
- Prediction validation/scoring over time (future feature)
- Canvas/Excalidraw integration with thinking sessions
- Importing existing notes as thinking sessions
