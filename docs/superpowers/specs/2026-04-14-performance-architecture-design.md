# Performance Architecture — Make Alfred Fast

**Date:** 2026-04-14
**Branch:** redesign
**Approach:** B — systematic optimization across frontend and backend
**Goal:** Every page transition feels instant, every interaction responds without lag, initial load is fast, AI features start streaming quickly.

---

## Section 1: Frontend Bundle Surgery

### 1a. Heavy Library Isolation

Ensure all heavy libraries are behind `next/dynamic` with `ssr: false` so they only load when their page is visited:

| Library | Size estimate | Current location | Action |
|---------|--------------|-----------------|--------|
| Three.js + fiber + drei | ~700KB | universe, atheneum galaxy | Verify atheneum galaxy is dynamic-wrapped |
| react-force-graph-3d | ~200KB | universe | Already dynamic. OK. |
| @xyflow/react | ~200KB | zettel-graph.tsx | Wrap in dynamic with ssr: false |
| @excalidraw/excalidraw | ~800KB | excalidraw-whiteboard.tsx | Already dynamic. OK. |
| recharts | ~200KB | components/ui/chart.tsx | Only loads if Chart used. Low priority. |

### 1b. Editor Consolidation

Remove BlockNote from think/session-editor.tsx. Replace with TipTap (the standard editor across the app — notes, documents, AI panel). Saves ~200-300KB from the think route chunk.

### 1c. Skeleton Loading States

Add page-level skeletons for 5 most-visited pages (knowledge, notes, documents, dictionary, dashboard). Each matches actual layout to prevent layout shift. Render while primary query is loading.

---

## Section 2: Data Fetching Overhaul

### 2a. Global staleTime Tuning

| Query | Current | Proposed | Rationale |
|-------|---------|----------|-----------|
| Canvas detail | 0s | 30s | Single-user editor, mutations invalidate |
| Notes detail | 0s | 15s | Same |
| Notion markdown | 0s | 60s | External, low change frequency |
| Zettel search | 5s | 30s | Changes only on create/update |
| Documents explorer/recent | 10s | 30s | Match global default |

### 2b. Route-Level Prefetching on Sidebar Hover

Create prefetchRouteData utility mapping routes to primary query options. Trigger on sidebar link mouseEnter. Requires extracting queryOptions objects from each feature's queries.ts.

Target routes: /knowledge, /notes, /documents, /universe, /dictionary, /research, /today, /dashboard.

### 2c. keepPreviousData on All List Queries

Add placeholderData: keepPreviousData to: documents explorer, notes workspaces, dictionary entries, research reports, learning daily deck. Shows last-known data instantly on return visits.

### 2d. Smarter Task Polling

Replace fixed 2s refetchInterval with exponential backoff: 1s, 2s, 4s, 8s, 10s cap. Most tasks complete within 2-3 polls.

---

## Section 3: Backend Query and Caching Fixes

### 3a. Replace find_similar_cards O(n) Scan with Qdrant

Current (zettelkasten_service.py:829-846): loads every card from Postgres, computes cosine similarity in Python loop. O(n).

Proposed: call qdrant_client.search() with the card's embedding vector. Returns top-k results in milliseconds. Fall back to Python path if Qdrant unreachable.

### 3b. Fix Agent Thread N+1

Current (api/agent/routes.py:317-318): for each session, fetches ALL messages just to count them. 51 queries for 50 threads.

Proposed: single query with correlated COUNT subquery. 1 query total.

### 3c. Move Canvas Diagram Generation to Celery

Current (api/canvas/routes.py:54): model.invoke() blocks FastAPI worker 3-10s.

Proposed: create tasks/canvas_tasks.py with generate_diagram_task. Route returns task ID immediately. Frontend polls with useTaskStatus (using new backoff from 2d).

### 3d. Redis Response Caching for List Endpoints

Extend existing _cache_get/_cache_set pattern from zettels routes into reusable core/cache.py:

| Endpoint | TTL | Invalidation |
|----------|-----|-------------|
| GET /api/zettels/cards | 60s | Zettel create/update/delete |
| GET /api/documents/explorer | 60s | Document create/update/delete |
| GET /api/agent/threads | 30s | Thread create/message send |
| GET /api/zettels/topics | 3600s | Already cached, keep |
| GET /api/zettels/tags | 3600s | Already cached, keep |

### 3e. HTTP Cache-Control Headers

Add Cache-Control: private, max-age=30 to list endpoints via FastAPI dependency. Browser skips request entirely for 30s, working with React Query staleTime.

---

## Section 4: Rendering and Image Optimization

### 4a. Memoize Shell Components

Wrap in React.memo: SidebarNavItem (14 instances), TopBar, TaskCenterButton.

### 4b. Fix Over-Subscription in SidebarNavItem

Currently every SidebarNavItem subscribes to useShellStore for AI panel state. Only the Alfred AI item needs it. Lift AI state to AppSidebar, pass as props only to the AI item. 13 items stop subscribing to shell store.

### 4c. Sidebar Hover Prefetch Integration

Add onMouseEnter to SidebarNavItem calling prefetchRouteData from Section 2b. Requires useQueryClient in AppSidebar, passed as prop.

### 4d. Image Optimization

No images in app routes currently. Low priority. Set the pattern with next/image when images are added.

---

## Expected Impact

| Optimization | Metric | Estimated gain |
|-------------|--------|---------------|
| Bundle surgery (1a, 1b) | Initial JS payload | -500KB to -1MB |
| Skeletons (1c) | Perceived load time | Eliminates blank screens |
| staleTime tuning (2a) | Unnecessary refetches | -40-60% network requests |
| Hover prefetch (2b, 4c) | Page transition time | Near-instant sidebar nav |
| keepPreviousData (2c) | Return-visit transitions | No blank screen |
| Qdrant search (3a) | suggest_links response | Seconds to under 50ms |
| N+1 fix (3b) | Thread list response | 51 queries to 1 |
| Celery diagrams (3c) | Canvas responsiveness | Unblocks FastAPI worker |
| Redis caching (3d) | List endpoint latency | -80% for cache hits |
| Cache-Control (3e) | Network requests | Browser skips for 30s |
| Memoization (4a, 4b) | Re-render count | -70% sidebar/shell renders |

## Out of Scope (Future)

- Optimistic updates on mutations
- Service Worker for offline caching
- SSE/WebSocket to replace all polling
- Server Components for list pages
- Database read replicas
