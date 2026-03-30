# Alfred Performance Optimization — Design Spec

**Date:** 2026-03-29
**Branch:** `performance`
**Scope:** Full-stack deep pass — backend, frontend, cross-cutting

## Context

Alfred has grown organically across multiple feature branches (agent chat, connectors, document pipeline, research). Performance was never the primary concern during feature development. This spec addresses 25+ identified bottlenecks across both stacks, organized into a three-phase "Foundation + Flows" approach.

### Guiding Principles

- **Fix systemic multipliers first** — a missing index or bad store pattern affects every feature
- **Each phase is independently shippable** — no phase depends on another being complete
- **Measure before and after** — every change should have a clear "was X, now Y" metric
- **No functional regressions** — performance work must not break existing behavior

---

## Phase 1: Foundation (Systemic Fixes)

Lifts the performance floor for the entire app. Low-risk, high-leverage changes.

### 1.1 Backend Foundation

#### Database Indexes & Query Fixes

**Add missing index on `pipeline_status`:**
- File: `app/models/doc_storage.py`
- Column `pipeline_status` is used in WHERE clauses but has no index
- Add: `sa.Index("ix_documents_pipeline_status", "pipeline_status")`
- Create Alembic migration

**Fix N+1 in document enrichment:**
- File: `app/tasks/document_enrichment.py:69-73`
- `_create_zettel_from_enrichment()` loads all ~1000 zettel cards to check for 1 duplicate
- Replace with: `SELECT 1 FROM zettels WHERE document_id = ? AND title = ? LIMIT 1`

**Fix N+1 in zettel bulk update:**
- File: `app/api/zettels/routes.py:87-95`
- Loop calls `get_card()` one at a time for each zettel in the batch
- Replace with: single query `SELECT * FROM zettels WHERE id IN (?)`

#### LLM Call Safety

**Add timeouts to all OpenAI calls:**
- File: `app/services/llm_service.py:93-98`
- Currently no timeout — calls can hang indefinitely
- Add `timeout=30` to all `client.chat.completions.create()` calls

**Normalize LLM factory cache keys:**
- File: `app/core/llm_factory.py:13-41`
- Different temperature values create different cache keys, causing cache misses
- Cache by `(provider, model)` only; pass temperature at call site

#### Blocking I/O → Async

**Move Firecrawl scraping to Celery:**
- File: `app/api/documents/routes.py:205-209`
- `fetch_and_organize()` blocks a FastAPI worker for 5-30+ seconds on external API call
- Move to Celery task, return task ID, let frontend poll for completion

**Move OpenAI image generation to background:**
- File: `app/api/documents/routes.py:280-310`
- `generate_document_image()` blocks 15-60 seconds
- Move to Celery task with polling endpoint

**Move planning LLM call to async:**
- Files: `app/services/planning_service.py:54`, `app/api/intelligence/routes.py:40-57`
- `create_plan()` makes a 3-30 second synchronous LLM call in an HTTP handler
- Convert to async endpoint: return task ID immediately, frontend polls `GET /intelligence/plan/{task_id}` for result (consistent with other async patterns in this spec)

#### Celery Optimization

**Use `celery.group()` for batch dispatch:**
- File: `app/tasks/document_title_image.py:61-84`
- Currently loops with `task.delay()` for each document
- Replace with `celery.group([task.s(doc_id) for doc_id in doc_ids])()`

### 1.2 Frontend Foundation

#### Zustand Store Pattern Fix

**Add `useShallow()` selectors to all store subscriptions:**
- All components consuming Zustand stores currently re-render on ANY state change
- Wrap all `useXxxStore()` calls with selectors: `useAgentStore(useShallow(s => ({ messages: s.messages, isStreaming: s.isStreaming })))`
- Audit every store consumer across the app

**Normalize agent store message storage:**
- File: `web/lib/stores/agent-store.ts`
- Current: O(n) array `.map()` on every token flush (every 50ms) to append to last message
- Replace with: indexed message map `Record<number, AgentMessage>` keyed by message ID, with a separate `messageOrder: number[]` array for render order
- Derive the messages array via a memoized selector: `useMemo(() => messageOrder.map(id => messagesById[id]), [messageOrder, messagesById])`
- Token flush only mutates one entry in `messagesById` — no array copy, selector cache stays valid for all other messages

#### React Rendering Fixes

**Memoize list item components:**
- `React.memo()` on: `MessageBubble`, `ReportListItem`, and any other component rendered in a `.map()` loop
- Files: `web/app/(app)/agent/_components/agent-chat-client.tsx`, `web/app/(app)/research/_components/research-client.tsx`

**Stabilize callback references:**
- `useCallback()` on all event handlers passed as props to memoized children
- Eliminate inline arrow functions in `.map()` renders (e.g., `onClick={() => onSelect(report.id)}`)

#### Bundle Splitting

**Dynamic import Three.js:**
- Three.js + react-three-fiber + drei are loaded unconditionally for all pages
- Move to `next/dynamic` import, only load on document visualization page
- Expected savings: ~500KB+ from initial bundle

**Dynamic import TipTap editor:**
- 9 TipTap extension packages loaded for all pages
- Lazy-load only on notes/editor pages

**Verify Excalidraw lazy loading:**
- Already partially dynamic — verify it's fully code-split and not pulled into main bundle

#### Progressive Rendering

**Add `loading.tsx` skeletons for major routes:**
- `web/app/(app)/dashboard/loading.tsx`
- `web/app/(app)/documents/loading.tsx`
- `web/app/(app)/research/loading.tsx`
- `web/app/(app)/agent/loading.tsx`
- `web/app/(app)/notes/loading.tsx`

**Add `<Suspense>` boundaries:**
- Wrap data-dependent sections in each page with `<Suspense fallback={<Skeleton />}>`
- Currently only 1 Suspense boundary in the entire app (Notion callback page)

---

## Phase 2: Hot Path Optimization (Flow-by-Flow)

Targeted optimizations for the most-used user journeys.

### 2.1 Agent Chat Streaming

**Token flush rate limiting:**
- File: `web/lib/stores/agent-store.ts:83-111`
- Increase token buffer flush interval from 50ms to 100-150ms
- Reduces render frequency by 2-3x with imperceptible UX difference

**Streaming content isolation:**
- Store actively-streaming content in a `useRef` outside React state
- Only commit to the messages array on stream completion or natural pauses
- Eliminates per-token state updates entirely during active streaming

**Message list render isolation:**
- Only the actively-streaming message bubble should re-render during streaming
- Use stable keys + `React.memo()` so completed messages never re-render

**Tool call state separation:**
- Move `activeToolCalls` to a separate Zustand slice
- Tool call UI updates should not trigger message list re-renders

### 2.2 Document Pipeline

**Progress tracking for async scraping:**
- After moving scraping to Celery (Phase 1), add Redis-backed progress tracking
- Frontend polls or subscribes via SSE for real-time status updates

**Semantic map optimization:**
- File: `app/api/documents/routes.py:426-438`
- Reduce default embedding limit from 20K to 2K
- Add server-side pagination for semantic map data
- Cache computed 3D projections in Redis with version-key invalidation

**Semantic map cache fix:**
- File: `app/services/doc_storage/_semantic_map_mixin.py:115-124`
- Currently runs `SELECT MAX(updated_at)` on every request even when cache is valid
- Replace with Redis version key: update version on document change, check version string instead of querying DB

**Document detail staleTime:**
- File: `web/features/documents/queries.ts`
- Currently `staleTime: 0` — refetches on every component mount
- Change to `staleTime: 30_000` (30s) to match app default

### 2.3 Page Navigation & Dashboard

**Eliminate data fetching waterfalls:**
- Canvas workbench: `useCanvas(selectedCanvasId)` waits for `useCanvasList()` to resolve
- Prefetch canvas detail alongside list query when `selectedCanvasId` is known from URL params

**AI panel thread caching:**
- File: `web/app/(app)/_components/ai-panel.tsx:86-95`
- `loadThreads()` fires every time `aiPanelOpen` changes
- Cache threads in store, only re-fetch if stale (>60s) or on explicit refresh

**Route prefetching:**
- Add `prefetch` to sidebar `<Link>` components for primary navigation routes
- Enables Next.js to preload route bundles on hover/viewport

### 2.4 Research Flow

**Memoize report list:**
- `React.memo()` on `ReportListItem`
- Extract `onClick` to `useCallback` with stable reference

**Prefetch on hover:**
- Prefetch report detail data on hover/focus of list items
- Uses React Query `queryClient.prefetchQuery()` for instant navigation feel

**Parallel fetch verification:**
- Verify report list + selected report detail queries don't waterfall

---

## Phase 3: Polish

Final optimization layer — bundle analysis, paint performance, cache strategy.

### 3.1 Bundle Analysis & Trimming

- Run `@next/bundle-analyzer` to get actual weight distribution
- Tree-shake unused Radix UI components
- Evaluate `pdf-lib` — dynamic import if only used in one place
- Check for duplicate dependency versions

### 3.2 CSS Paint Performance

**Grain texture overlay:**
- File: `web/app/globals.css:321-332`
- `body::before` with fixed-position SVG background causes continuous paint
- Fix: add `will-change: transform` to promote to compositor layer (GPU-accelerated)
- Alternative: conditionally disable on heavy interactive pages (agent chat)

**Landing page animations:**
- `arcane-float`, `arcane-spin` run indefinitely
- Add `animation-play-state: paused` when off-screen via IntersectionObserver
- Respect `@media (prefers-reduced-motion: reduce)`

### 3.3 Cache Strategy Standardization

Standardize React Query `staleTime` across the app:

| Data Category | staleTime | Examples |
|---|---|---|
| Real-time | `0` | Active SSE streams, agent messages during streaming |
| User content | `30_000` (30s) | Documents, zettels, research reports |
| Computed/expensive | `300_000` (5min) | Semantic map, embedding projections |
| Static-ish | `600_000` (10min) | Connector status, user settings |

Backend: Redis cache for semantic map computations with version-key invalidation.

### 3.4 Response Optimization

- Evaluate streaming JSON for large list endpoints (documents, zettels)
- Add gzip/brotli compression middleware to FastAPI if not present
- Verify HTTP/2 and `Connection: keep-alive` between frontend and backend

---

## Files Affected (Estimated)

### Backend (~15 files)
- `app/models/doc_storage.py` — add index
- `app/tasks/document_enrichment.py` — fix N+1
- `app/api/zettels/routes.py` — fix N+1
- `app/services/llm_service.py` — add timeouts
- `app/core/llm_factory.py` — normalize cache keys
- `app/api/documents/routes.py` — async scraping + image gen + semantic map pagination
- `app/services/planning_service.py` — async LLM
- `app/api/intelligence/routes.py` — async endpoint
- `app/tasks/document_title_image.py` — celery.group()
- `app/services/doc_storage/_semantic_map_mixin.py` — Redis cache
- New Alembic migration for index
- New Celery tasks for scraping/image gen

### Frontend (~20 files)
- `web/lib/stores/agent-store.ts` — normalize messages, selectors, flush rate
- `web/app/(app)/agent/_components/agent-chat-client.tsx` — memoization
- `web/app/(app)/research/_components/research-client.tsx` — memoization
- `web/app/(app)/_components/ai-panel.tsx` — thread caching
- `web/app/(app)/canvas/_components/canvas-workbench-client.tsx` — parallel fetch
- `web/features/documents/queries.ts` — staleTime fix
- `web/app/globals.css` — paint optimization
- `web/next.config.js` — bundle analyzer
- 5x new `loading.tsx` files
- All components consuming Zustand stores — add selectors
- Dynamic import wrappers for Three.js, TipTap

---

## Success Criteria

- No functional regressions — all existing features work identically
- Agent chat streaming: no visible jank during token streaming
- Page navigation: sub-200ms perceived load time for cached routes
- Document pipeline: no blocked FastAPI workers during scraping/image gen
- Bundle: initial JS payload reduced by 30%+ (Three.js alone is ~500KB)
- Database: no N+1 queries in hot paths
- LLM calls: all have timeouts, none block HTTP workers

---

## Async Task Polling Pattern

All endpoints converted from sync to Celery (scraping, image gen, planning) follow the same pattern:

1. `POST /endpoint` — enqueues Celery task, returns `{ "task_id": "abc123", "status": "pending" }`
2. `GET /tasks/{task_id}` — returns `{ "status": "pending|running|completed|failed", "result": ... }`
3. Frontend polls `GET /tasks/{task_id}` every 2s until `status` is `completed` or `failed`
4. Shared `useTaskPolling(taskId)` React hook handles the polling + cleanup

This avoids building three separate polling mechanisms.

---

## Out of Scope

- Database schema redesign or major model changes
- New features or UI changes beyond loading skeletons
- Infrastructure changes (Redis cluster, CDN, etc.)
- SSR/ISR strategy changes
- Migration to a different state management library
