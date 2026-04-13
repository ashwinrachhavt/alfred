# Streaming Zettel Creation

**Date:** 2026-04-12
**Status:** Draft
**Branch:** redesign

## Problem

Zettel creation is a dead interaction. You fill a form, hit create, get a spinner, and see a card. No AI enrichment, no connections surfaced, no learning moment. Embeddings are lazy (generated on-demand), link suggestions are a separate manual action, and knowledge gaps are invisible.

The goal: make zettel creation feel like interactive studying. The AI works visibly — streaming its reasoning, searching your knowledge base, finding connections, enriching your card — all in real-time inside a modal.

## Approach

**Streaming Orchestrator Endpoint** — a new SSE endpoint that saves the card immediately, then runs two concurrent async tracks (linking chain + AI analysis), streaming every step back to a frontend modal.

Chosen over:
- Celery + WebSocket (overengineered for throughput, can't stream reasoning tokens)
- Reusing agent infrastructure (couples zettel creation to agent system, can't control step ordering)

## SSE Event Protocol

### Endpoint

```
POST /api/zettels/cards/create-stream
Content-Type: application/json
Body: ZettelCardCreate (same schema as existing POST /cards)

Response: text/event-stream
Headers: Cache-Control: no-cache, Connection: keep-alive, X-Accel-Buffering: no
```

### Event Sequence

| # | Event | Data | Phase |
|---|-------|------|-------|
| 1 | `card_saved` | `{id, title, status}` | 0 |
| 2 | `thinking` | `{content}` (streamed incrementally) | 1B |
| 3 | `enrichment` | `{suggested_title?, summary?, tags?, topic?}` | 1B |
| 4 | `embedding_done` | `{card_id}` | 1A |
| 5 | `tool_start` | `{step: "searching_kb"}` | 1A |
| 6 | `links_found` | `{suggestions: [{card_id, title, score, reason}]}` | 1A |
| 7 | `links_created` | `{links: [{source_id, target_id, type}]}` | 1A |
| 8 | `decomposition` | `{is_atomic, reason, suggested_cards: [{title, content}]}` | 1B |
| 9 | `gaps` | `{missing_topics: [...], weak_areas: [{topic, existing_count, note}]}` | 1B |
| 10 | `done` | `{card: ZettelCardOut, stats: {links_created, gaps_found, ...}}` | 2 |
| err | `error` | `{step, message}` | any |

Events 2-9 interleave as tracks produce them. `card_saved` is always first. `done` is always last. Non-fatal `error` events don't kill the stream.

### SSE Format

```
event: card_saved
data: {"id": 42, "title": "PBFT vs Raft", "status": "active"}

event: thinking
data: {"content": "This content discusses distributed"}

event: thinking
data: {"content": " consensus algorithms. The user has"}

event: enrichment
data: {"suggested_title": "PBFT vs Raft: Byzantine Fault Tolerance Compared", "summary": "Compares...", "tags": ["consensus", "bft"], "topic": null}

event: embedding_done
data: {"card_id": 42}

event: tool_start
data: {"step": "searching_kb"}

event: links_found
data: {"suggestions": [{"card_id": 7, "title": "Raft Leader Election", "score": 0.91, "reason": "Both discuss consensus leader selection"}]}

event: done
data: {"card": {...}, "stats": {"links_created": 2, "gaps_found": 1}}
```

## Backend Pipeline Architecture

### Execution Graph

```
POST /api/zettels/cards/create-stream
|
+- Phase 0: Save card to DB (sync, via asyncio.to_thread)
|  +- emit card_saved
|
+- Phase 1: asyncio.gather(Track A, Track B)
|  |
|  +- Track A: Linking Chain (sequential)
|  |  +- Generate embedding (asyncio.to_thread -> OpenAI embedding API)
|  |  |  +- emit embedding_done
|  |  +- Sync to Qdrant vector index (asyncio.to_thread)
|  |  +- Search Qdrant for similar cards (asyncio.to_thread)
|  |  |  +- emit tool_start, links_found
|  |  +- Auto-create links for score >= 0.75 (asyncio.to_thread)
|  |     +- emit links_created
|  |
|  +- Track B: AI Analysis (single streamed o4-mini call)
|     +- Fetch lightweight context (topic/tag distribution from Redis cache)
|     +- Stream reasoning tokens -> emit thinking
|     +- Parse structured JSON completion -> emit enrichment, decomposition, gaps
|     +- If Track A similar cards available via asyncio.Event, include in prompt context
|
+- Phase 2: Finalize
   +- Invalidate caches (topic/tag/graph)
   +- emit done with full card state
```

### New Files

| File | Purpose |
|------|---------|
| `apps/alfred/services/zettel_creation_stream.py` | `ZettelCreationStream` orchestrator class |
| `apps/alfred/api/zettels/stream_routes.py` | SSE endpoint (mounted in existing zettels router) |
| `apps/alfred/utils/async_merge.py` | `merge_async_generators()` utility |
| `web/lib/stores/zettel-creation-store.ts` | Zustand store for streaming state |
| `web/app/(app)/knowledge/_components/zettel-creation-modal.tsx` | Streaming modal component |

### Modified Files

| File | Change |
|------|--------|
| `apps/alfred/api/zettels/routes.py` | Mount stream routes |
| `apps/alfred/services/zettelkasten_service.py` | Extract embedding/linking methods for reuse (no logic change) |
| `web/features/zettels/mutations.ts` | Add `useCreateZettelStream` hook |
| `web/lib/api/zettels.ts` | Add `createZettelStream()` SSE client |
| `web/lib/api/routes.ts` | Add stream route |

### Async Patterns

| Operation | Pattern | Rationale |
|-----------|---------|-----------|
| DB insert/update | `asyncio.to_thread()` | SQLModel is sync |
| Embedding generation | `asyncio.to_thread()` | Langchain embedding client is sync |
| Qdrant search/sync | `asyncio.to_thread()` | Qdrant client is sync |
| LLM streaming (o4-mini) | `openai.AsyncClient` | Native async streaming for reasoning tokens |
| Redis cache reads | `asyncio.to_thread()` | Fast but sync |
| Cache invalidation | `asyncio.to_thread()` | Same |

### Session Management

Each concurrent track gets its own DB session via `next(get_db_session())`. SQLAlchemy sessions are not thread-safe across `asyncio.to_thread()` boundaries. The main session is used only for Phase 0 (card insert), then closed before Phase 1 begins.

### Error Isolation

Each track is wrapped in try/except. Failures emit `error` events but don't terminate the stream. If Track A fails (Qdrant unreachable), the user still gets AI enrichment from Track B. If Track B fails (LLM timeout), the user still gets their card + links.

## AI Prompt & Model Strategy

### Model

o4-mini — exposes reasoning tokens via `reasoning_content` in streaming responses. Fast (2-5s), cheap, good at structured analysis.

### Single Call Design

One LLM call handles enrichment + decomposition + gap detection. Three separate calls would mean 3x latency, 3x cost, and three disjointed thinking streams.

### Prompt

```
System: You are a knowledge analyst for a Zettelkasten system. The user is creating
a new knowledge card. Analyze it and provide enrichment, decomposition assessment,
and knowledge gap analysis.

You have access to the user's existing knowledge base context:
- Total cards: {count}
- Related cards (by embedding similarity): {similar_cards_summary}
- Existing topics: {topic_list}
- Existing tags: {tag_list}

User: New card being created:
Title: {title}
Content: {content}
Tags: {tags}
Topic: {topic}

Respond with JSON:
{
  "enrichment": {
    "suggested_title": "..." | null,
    "summary": "...",
    "suggested_tags": [...],
    "suggested_topic": "..." | null
  },
  "decomposition": {
    "is_atomic": true/false,
    "reason": "...",
    "suggested_cards": [{"title": "...", "content": "..."}]
  },
  "gaps": {
    "missing_topics": ["..."],
    "weak_areas": [{"topic": "...", "existing_count": N, "note": "..."}]
  }
}
```

### Context Injection

Track B needs knowledge base context for gap detection and tag suggestions:

1. **Fast DB aggregates** (available immediately): topic distribution, tag frequency, total card count. These are already cached in Redis.
2. **Similar cards from Track A** (available after embedding + search): passed via `asyncio.Event` + shared dict. If Track A finishes embedding/search before Track B makes the LLM call, similar cards are included in the prompt. If not, Track B works without them — gap detection still functions from topic/tag distribution alone.

## Frontend Modal Design

### States

1. **FORM** — Title, content, tags, topic fields (same as current creation form)
2. **STREAMING** — User hits "Create" → modal transitions to live streaming view
3. **COMPLETE** — All events received → show final card + actionable enrichment suggestions

### Streaming View Layout

```
+---------------------------------------------+
|  Creating Zettel                        X    |
+---------------------------------------------+
|                                              |
|  checkmark Card saved                        |
|                                              |
|  [AI Thinking] (collapsible, Berkeley Mono)  |
|  | This content discusses distributed        |
|  | consensus algorithms. The user has 4      |
|  | existing cards on Raft but none on        |
|  | PBFT...                                   |
|  | (streaming cursor)                        |
|                                              |
|  checkmark Embedding generated               |
|  spinner Searching knowledge base...         |
|                                              |
|  [Suggestions] (appears as events arrive)    |
|                                              |
|  Enrichment                                  |
|    Better title: "PBFT vs Raft..."   [v] [x] |
|    Summary: "Compares..."            [v] [x] |
|    +tag: consensus                   [v] [x] |
|                                              |
|  3 Links Found                               |
|    "Raft Leader Election" (0.91)     [v]     |
|    "CAP Theorem Notes" (0.84)        [v]     |
|    "Byzantine Generals" (0.78)       [v]     |
|                                              |
|  Knowledge Gaps                              |
|    No cards on: PBFT, BFT variants           |
|                                              |
|              [ Apply & Close ]               |
+---------------------------------------------+
```

### UX Decisions

- **Card saves immediately** — first checkmark in <200ms. If user closes modal early, card exists.
- **Thinking tokens** — collapsible block, Berkeley Mono font, `--alfred-text-tertiary` color. Collapsed by default, expandable for the studying feel.
- **Enrichments are opt-in** — accept/reject toggles per suggestion. Nothing auto-applied to card content except links above threshold.
- **Links >= 0.75 auto-created** — shown pre-checked, user can uncheck to remove. Unchecking triggers a DELETE on the link via the existing `DELETE /api/zettels/links/{id}` endpoint when "Apply & Close" is pressed.
- **"Apply & Close"** sends PATCH with accepted enrichments and DELETE requests for rejected auto-links. If the user closes without clicking "Apply & Close", auto-links persist (they were already created server-side) and enrichments are discarded.
- **Knowledge gaps are informational** — no action buttons, awareness only.
- **Early close is safe** — card exists from Phase 0. Enrichments are lost but card is complete.

### Implementation

- **Zustand store** (`zettel-creation-store.ts`): tracks streaming state, accumulated events, user selections (accepted/rejected enrichments and links)
- **EventSource connection**: same pattern as agent store — `fetch()` with `getReader()` for SSE parsing
- **Modal component**: shadcn `Dialog` for modal, `Collapsible` for thinking block, `Checkbox` for suggestion toggles
- **Apply endpoint**: `PATCH /api/zettels/cards/{id}` (already exists) to apply accepted enrichments

### Styling (per DESIGN.md)

- Thinking block: Berkeley Mono, `text-xs`, `--alfred-text-tertiary`, subtle `--alfred-ruled-line` border
- Progress steps: DM Sans, checkmark/spinner icons, left-aligned timeline
- Suggestions: card-style sections with `bg-card`, `border`, `rounded-md`
- Accept/reject: small toggle buttons, accent color for accepted
- Modal: `max-w-lg`, warm dark background matching knowledge page

## Scope Boundaries

### In scope (v1)
- SSE streaming endpoint with full event protocol
- Async orchestration with two concurrent tracks
- o4-mini reasoning token streaming
- Embedding generation on creation (no longer lazy)
- Auto link suggestion + creation
- Content enrichment (title, summary, tags, topic)
- Decomposition detection
- Knowledge gap surfacing
- Frontend streaming modal with opt-in enrichments

### Out of scope
- Batch creation streaming (one card at a time)
- Decomposition auto-execution (we suggest, user decides)
- Gap-driven card creation ("create a card about PBFT" from the gaps section)
- Persisting thinking tokens to DB
- Mobile/responsive modal layout
- Offline/retry handling for SSE disconnects
