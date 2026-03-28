# Alfred Frontend Revamp: Knowledge Factory

**Date:** 2026-03-20
**Branch:** `alfred-revamp`
**Approach:** New Shell, Migrate Internals

## Vision

Alfred is a knowledge factory. It ingests, decomposes, connects, and helps you think so you can capitalize on what you know. The frontend revamp reframes the UI around four pillars: **Inbox** (capture), **Canvas** (explore), **AI** (think), and **Dashboard** (measure).

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary experience | Knowledge Inbox | Gmail-like unified stream for knowledge |
| Inbox organization | Hybrid | Unified stream + filters by source, topic, processing stage |
| Knowledge visualization | Spatial Canvas | Infinite canvas with AI-suggested connections |
| AI interaction | Panel + embedded actions | Persistent conversational panel + contextual quick-actions |
| Dashboard metrics | Three-layer + score | Retention, Coverage, Connections = Knowledge Score |
| Navigation model | Hub-and-spoke | Inbox is gravity center; Canvas/AI/Dashboard in top bar; tools as panels |
| Execution approach | New Shell, Migrate Internals | New app shell + layout; reuse existing API client, queries, mutations, UI primitives |

## 1. App Shell & Navigation

### Layout

```
+-----------------------------------------------------------+
| Alfred    [Inbox] [Canvas] [AI] [Dashboard]    Cmd-K  [U] |  <- Top bar
+--------------------------------------------------+--------+
|                                                   |        |
|              Main content area                    | AI     |
|                                                   | Panel  |
|                                                   | (opt)  |
|                                                   |        |
+--------------------------------------------------+--------+
```

### Top Bar
- Slim, persistent across all pages.
- Four pillar icons + labels as primary navigation.
- Cmd-K command palette trigger on the right.
- User avatar / settings dropdown.

### AI Panel
- Collapsible right-side panel (~380px wide).
- Toggle via Cmd-J or top-bar icon.
- Available on every page. Context-aware (knows current page).
- When open, main content area shrinks to accommodate.

### Tool Panels
- Notes editor, Connector settings, Writing assistant, Learning/Quiz open as slide-over sheets from the right (~50-70% viewport width).
- They overlay the current page (z-index above main content, below modals). Closing returns to previous state.
- **Stacking rule:** Only one tool panel open at a time. Opening a tool panel auto-closes any existing tool panel. The AI panel and a tool panel CAN coexist (AI panel sits behind/beside the tool panel).
- No full-page navigation for tools (exception: System Design whiteboard gets full-screen takeover).

### Command Palette (Cmd-K)
- Search across documents, notes, zettels.
- Quick-nav to any pillar page.
- Trigger AI actions ("Summarize clipboard", "What do I know about X").
- Invoke connectors ("Import from Notion", "Sync Readwise").
- Access tools ("New note", "System Design", "Connectors").

### Responsive / Mobile
- **Desktop (>1024px):** Full layout as described. AI panel is a resizable sidebar.
- **Tablet (768-1024px):** Top bar collapses to icons only. AI panel becomes a full-height slide-over. Tool panels become full-width slide-overs.
- **Mobile (<768px):** Bottom tab bar replaces top bar (4 pillar icons). AI panel and tool panels are full-screen sheets. Canvas is touch-enabled with pinch-to-zoom.

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| Cmd-K | Open command palette |
| Cmd-J | Toggle AI panel |
| Escape | Close active panel / dialog |
| Cmd-1/2/3/4 | Navigate to Inbox / Canvas / AI / Dashboard |
| Cmd-N | New note (opens notes tool panel) |

Canvas-specific shortcuts are defined in Section 3.

### File Change Verbs
- **Replace:** Delete old file, create new file with same or different path. No code carried over.
- **Evolve:** Keep the file, refactor its internals to work in the new shell. Signature/API may change.
- **New:** File does not exist yet, create from scratch.
- **Keep:** No changes needed.

### Files Changed
- **Replace:** `app/(app)/layout.tsx`, `app/(app)/_components/app-shell.tsx`, `components/app-sidebar.tsx`
- **Evolve:** `components/app-command-palette.tsx`, `lib/navigation.ts`, `app/page.tsx` (root redirect to `/inbox`)
- **Keep:** `components/ui/*`, `middleware.ts`, `app/layout.tsx`, `app/providers.tsx`

## 2. Knowledge Inbox

**Route:** `/` (redirects to `/inbox`) and `/inbox`

### Stream
- Reverse-chronological unified stream of all ingested knowledge.
- Infinite scroll with cursor-based pagination.
- Each item shows: source icon, title, relative time, preview snippet (~120 chars), topic tags, processing stage badge, contextual quick-action button.

### Source Tabs
- Horizontal tabs above the stream: All | Articles | Highlights | Notes | Papers | ...
- Tabs are defined in a frontend connector registry (`lib/connector-registry.ts`) that maps known connectors to tab labels and icons. Each tab filters by `content_type` field on documents.
- "All" is the default.

### Filter Bar
- Below tabs: search input + dropdowns for Topic, Stage, Date range.
- Topic dropdown populated from document enrichment data (aggregated client-side from explorer results, or a new lightweight backend endpoint if volume warrants it).
- Stage dropdown: New, Decomposed, Connected, Retained.

### Backend Gaps (require backend changes)
The current `GET /api/documents/explorer` endpoint only supports `limit`, `cursor`, `filter_topic`, and `search`. The Inbox requires these additional filters:
- **`content_type`** — filter by source type (for source tabs). Add to explorer endpoint.
- **`stage`** — filter by processing stage (New/Decomposed/Connected/Retained). Requires a `stage` or `processing_status` field on DocumentRow, or derivation from enrichment/pipeline state.
- **`date_from` / `date_to`** — date range filter. Add to explorer endpoint (filter on `captured_at`).

These are additive backend changes (new query params on existing endpoint) and should be implemented before or alongside the frontend Inbox work.

### Item Interaction
- Click expands inline or opens a detail slide-over panel (not page navigation).
- Detail view shows: full content, enrichment data, related concepts, action buttons.
- Quick actions per stage: New -> Decompose, Decomposed -> Connect, Connected -> Review, Retained -> Quiz.

### Async Action Behavior
Quick actions like "Decompose" and "Enrich" are fire-and-forget Celery tasks. The UX flow:
1. User clicks action -> optimistic UI updates badge to "Processing..." state.
2. Frontend polls `GET /tasks/{task_id}` (existing endpoint) every 3s until complete.
3. On completion, update the item's stage badge and show a success toast.
4. On failure, revert badge and show error toast with retry option.

Reuse existing `features/tasks/task-tracker-provider.tsx` and `features/tasks/task-tracker.ts` for polling.

### Backend Endpoints
All paths below are the **frontend-facing** URLs (prefixed with `/api/`). Next.js rewrites strip or remap prefixes as needed to reach the backend.

- Stream: `GET /api/documents/explorer` (paginated, cursor-based — needs extension, see Backend Gaps)
- Search: `GET /api/documents/search`
- Quick actions: `POST /api/pipeline/{id}/replay`, `POST /api/documents/doc/{id}/enrich`
- Task polling: `GET /api/tasks/{task_id}`

### Frontend API Client Changes
`lib/api/routes.ts` needs new entries:
- `documents.search` -> `/api/documents/search`
- `documents.enrich` -> (id) => `/api/documents/doc/${id}/enrich`
- `documents.pageExtract` -> `/api/documents/page/extract`
- `rag.answer` -> `/api/rag/answer` (Next.js rewrite maps to backend `/rag/answer`)
- `zettels.cards` -> `/api/zettels/cards`
- `zettels.graph` -> `/api/zettels/graph`
- `zettels.suggestLinks` -> (id) => `/api/zettels/cards/${id}/suggest-links`
- `intelligence.summarizeText` -> `/api/intelligence/summarize/text`
- `intelligence.summarizeUrl` -> `/api/intelligence/summarize/url`
- `intelligence.qa` -> `/api/intelligence/qa`
- `pipeline.replay` -> (id) => `/api/pipeline/${id}/replay`
- `pipeline.status` -> (id) => `/api/pipeline/${id}/status`
- `whiteboards.list` -> `/api/whiteboards`
- `whiteboards.byId` -> (id) => `/api/whiteboards/${id}`
- `connectors.status` -> (name) => `/api/${name}/status`
- `mindPalace.query` -> `/api/mind-palace/agent/query`

### Files Changed
- **New:** `app/(app)/inbox/` route group, `lib/connector-registry.ts`
- **Evolve:** `lib/api/routes.ts` (add missing endpoint entries listed above)
- **Reuse:** `features/documents/queries.ts`, `features/documents/mutations.ts`, `lib/api/documents.ts`, `features/tasks/task-tracker-provider.tsx`

## 3. Knowledge Canvas

**Route:** `/canvas` (default canvas) and `/canvas/[canvasId]` (specific canvas)

### Canvas Nodes (three types)
- **Documents** — ingested articles, papers, highlights from doc store. Identified by document UUID. Fetched from `/api/documents/explorer`.
- **Concepts** — extracted concepts from the pipeline. These live inside the `concepts` JSON field on DocumentRow (populated by the concept extraction pipeline). Each concept is identified by a composite key: `{documentId}:{conceptIndex}`. The frontend extracts concept nodes from document enrichment data when loading the canvas. A concept node displays: concept name, brief description, parent document reference.
- **Zettels** — user-authored atomic notes from zettelkasten. Identified by zettel card ID. Fetched from `/api/zettels/cards`.

### Edges
- Solid lines: explicit user-created links.
- Dashed lines: AI-suggested connections (click to confirm/dismiss).

### Interactions
- Drag items from Inbox onto the canvas to place them.
- Cmd-click two nodes to manually link them.
- AI Suggest toggle: when ON, AI proposes dashed-line connections with rationale on hover.
- Double-click a node to expand into a reading/editing panel (inline).
- [+] button: create zettel, drop URL, paste text.

### Bottom Bar
- View toggles: Documents, Concepts, Zettels, or All.
- Minimap for orientation.
- Canvas selector dropdown: switch between named canvases, create new, rename, delete.

### Canvas Management
- `/canvas` loads the user's most recent canvas (or creates a default one).
- `/canvas/[canvasId]` loads a specific canvas by whiteboard ID.
- Canvas selector in the bottom bar shows all canvases (from `GET /api/whiteboards`).
- Create/rename/delete via `POST /api/whiteboards`, `PATCH /api/whiteboards/{id}`.

### Canvas Persistence
- Saved per user. Multiple named canvases supported.
- Each canvas stored as a whiteboard via `/api/whiteboards` with `scene_json` containing node positions, edges, and viewport state.
- Auto-save on change (debounced 2s) via `POST /api/whiteboards/{id}/revisions`.

### Tech Choice
- **Primary:** `@xyflow/react` (formerly `reactflow`) for the node-graph UI. Purpose-built for interactive node graphs, supports custom node components. ~150-200KB minified.
- **Aspiration:** Integrate Tiptap mini-editors inside custom nodes so notes and diagrams coexist natively.
- **Fallback:** If native integration proves infeasible, `@xyflow/react` for graph + Tiptap in slide-over for editing.
- **Excalidraw:** Preserved for System Design whiteboard only (full-screen tool panel).

### Backend Endpoints
- Nodes: `GET /api/documents/explorer`, `GET /api/zettels/cards`, concept data from enrichment
- Edges: `GET /api/zettels/cards/{id}/links`, `POST /api/zettels/cards/{id}/suggest-links`
- Canvas state: `GET /api/whiteboards`, `POST /api/whiteboards`, `PATCH /api/whiteboards/{id}`, `POST /api/whiteboards/{id}/revisions`
- AI suggestions: `POST /api/intelligence/qa` or agent endpoint

### Files Changed
- **New:** `app/(app)/canvas/` route group with `[canvasId]` dynamic segment
- **Reuse:** `features/documents/queries.ts`, `features/notes/queries.ts`
- **Evolve/Remove:** `app/(app)/documents/_components/atheneum/galaxy-view.tsx` (Three.js galaxy view superseded)

## 4. AI Panel & Embedded Actions

### Persistent Panel (Cmd-J)
- Right-side collapsible panel, ~380px wide.
- Conversational RAG interface: ask questions, get answers citing user's documents.
- Source citations are clickable (open document in detail view).
- Proactive suggestions: knowledge gaps, connection opportunities, review reminders.
- Context-aware: behavior adapts to current page (Inbox: triage help, Canvas: connection suggestions, Dashboard: metric explanations).
- Streaming responses via SSE.

### Embedded Quick Actions
| Surface | Actions |
|---------|---------|
| Inbox item | Decompose, Summarize, Extract concepts, Find related |
| Canvas node | Explain, Connect to..., Expand children, Quiz me |
| Document detail | TL;DR, Key takeaways, Generate zettels, Suggest tags |
| Dashboard gap | Find resources, Create study plan, Start quiz |

Each action triggers a backend endpoint. Async actions (enrich, pipeline) use the task polling pattern described in Section 2. Synchronous actions (summarize, detect language) show results inline immediately.

### Backend Endpoints
All paths are frontend-facing (prefixed with `/api/`):
- Chat: `GET /api/rag/answer` (Next.js rewrite maps to backend `/rag/answer`)
- Chat (alt): `POST /api/intelligence/qa`
- Streaming: `POST /api/writing/compose/stream` (existing SSE endpoint for real-time generation). For RAG chat, use `/api/intelligence/qa` with a wrapper that streams via the AI panel's message state. If true SSE is needed for RAG, a new `POST /api/rag/stream` backend endpoint will be required (out of scope for initial revamp — use non-streaming `/api/rag/answer` first).
- Summarize: `POST /api/intelligence/summarize/text`, `POST /api/intelligence/summarize/url`, `POST /api/intelligence/summarize/pdf`
- Actions: `POST /api/documents/doc/{id}/enrich`, `POST /api/pipeline/{id}/replay`, `POST /api/zettels/cards/{id}/suggest-links`
- Agent: `POST /api/mind-palace/agent/query`

### Files Changed
- **New:** AI panel component (replaces `components/assistant-sheet.tsx`)
- **Reuse:** `lib/api/intelligence.ts`, `lib/api/routes.ts`

## 5. Dashboard

**Route:** `/dashboard`

### Knowledge Score (Hero)
- Single 0-100 number at the top, computed client-side from three sub-scores.
- **Formula:** `score = 0.4 * retention + 0.3 * coverage + 0.3 * connections` (weights stored in a constant, tunable later).
- **Sub-score normalization:**
  - Retention (0-100): directly from `/api/learning/metrics/retention` (`retention_rate_30d * 100`). If no data, default to 0.
  - Coverage (0-100): `min(100, uniqueTopics * 10)` — rewards breadth up to 10 topics, then capped. Computed from topic summary data.
  - Connections (0-100): `min(100, (edgeCount / max(nodeCount, 1)) * 25)` — rewards density up to 4 edges/node average. Computed from `/api/zettels/graph`.
- Week-over-week delta shown (requires storing previous score in localStorage).

### Retention Card
- Decay curves (recharts line chart).
- Count of concepts due for review, fading, strong.
- "Start Review Session" button opens quiz/flashcard slide-over panel.
- **Data sources:**
  - `GET /api/zettels/reviews/due` — zettel cards due for spaced-repetition review. Drives the "due for review" count and the flashcard session.
  - `GET /api/learning/metrics/retention` — overall 30-day retention rate and sample size. Drives the hero percentage in the decay chart and the "strong" count.
  - Both systems (zettels + learning) contribute to the Retention sub-score. The Retention Card displays data from both: the learning retention rate for the chart, zettel due count for the action button.

### Coverage Card
- Topic heatmap (treemap or bar chart).
- Topics sized by document count, colored by depth.
- "Explore Gaps" triggers AI to suggest resources for weak areas.
- **Data source:** Requires a **new backend endpoint** `GET /api/documents/topics/summary` that returns aggregated topic counts (e.g., `[{topic: "ML", count: 47}, ...]`). This avoids fetching all documents client-side. Implementation: a simple `SELECT topics->>'primary' as topic, COUNT(*) FROM documents GROUP BY 1` query in the doc storage service. Until this endpoint exists, fallback: fetch first 500 documents from explorer and aggregate client-side (acceptable for early usage).

### Connections Card
- Graph density metric (edges/node).
- Orphan concept count, bridge idea count.
- Strongest cluster identification.
- Mini force-directed graph preview (top 50 nodes) — rendered with `@xyflow/react` in read-only mode (same lib as Canvas).
- "Connect Orphans" and "Open Canvas" action buttons.
- **Data source:** `GET /api/zettels/graph` (returns nodes + edges arrays).

### Activity Strip
- 7-day sparkline: items ingested, decomposed, connected, reviewed.
- **Data source:** computed client-side from document `captured_at` timestamps (recent 7 days from explorer).

### Files Changed
- **Replace:** `app/(app)/dashboard/` (new dashboard layout)
- **Reuse:** `features/dashboard/dashboard-layout.ts` (concept), recharts

## 6. Feature Migration Map

### Tools as Panels (not pages)
| Feature | Access Method | Panel Type | Migrated From |
|---------|--------------|------------|---------------|
| Notes editor | Click note/zettel, Cmd-K "New note" | Slide-over (70%) | `app/(app)/notes/` |
| Document reader | Click inbox item | Slide-over (50%) | `app/(app)/documents/[id]/` |
| Writing assistant | Cmd-K "Compose", embedded action | AI panel mode switch | `app/(app)/` (was not a page) |
| System Design | Cmd-K "System Design" | Full-screen page navigation (navigates to `/system-design/sessions`) | `app/(canvas)/system-design/` (kept as-is, this is the ONE exception to the no-page-navigation rule because Excalidraw genuinely requires full viewport) |
| Connectors | Cmd-K "Connectors", Settings gear | Slide-over settings | New |
| Notion sync | Under Connectors | Sub-panel | `app/(app)/notion/` |
| Research | Cmd-K "Deep Research", inbox action | AI panel long-running task | `app/(app)/research/` |
| Learning/Quiz | Dashboard "Start Review", Cmd-K "Quiz" | Slide-over flashcard flow | New (uses learning API) |

### Pages Removed
| Page | Reason | Replacement |
|------|--------|-------------|
| `/calendar` | Job-search era artifact | Calendar events flow into Inbox if connector active |
| `/rag` | Separate RAG page redundant | AI panel IS the RAG interface |
| `/library` | Separate library redundant | Inbox IS the library |
| `/design-system` | Developer tool | Accessible via Cmd-K only |
| `/tasks` | Background tasks view | Task status shown in toasts / AI panel |

### Code Preserved (no changes needed)
- `lib/api/*` — all API client code and types
- `features/*/queries.ts` and `features/*/mutations.ts` — all TanStack Query hooks
- `components/ui/*` — all shadcn/ui primitives
- `components/editor/markdown-notes-editor.tsx` — Tiptap editor
- `components/system-design/*` — Excalidraw canvas and related
- `app/providers.tsx` — TanStack Query + theme providers
- `hooks/use-mobile.ts`, `hooks/use-now.ts` — utility hooks
- Clerk auth middleware and sign-in/sign-up pages

## 7. New Dependencies

| Package | Purpose | Size (minified) |
|---------|---------|------|
| `@xyflow/react` | Interactive node-graph canvas (formerly `reactflow`) | ~150-200KB |

No other new dependencies anticipated. Existing stack (Next.js 16, React 19, Tailwind 4, shadcn, TanStack Query, Tiptap, recharts, Zustand) covers all needs.

## 8. Zustand Stores (New)

### `useShellStore`
```ts
{
  aiPanelOpen: boolean;          // Cmd-J toggle
  toolPanel: {                   // Currently open tool panel (null if none)
    type: 'notes' | 'document' | 'connectors' | 'quiz' | 'writing';
    props: Record<string, unknown>;  // Context-specific props (e.g., documentId)
  } | null;
  toggleAiPanel: () => void;
  openToolPanel: (type, props) => void;
  closeToolPanel: () => void;
}
```

### `useAiPanelStore`
```ts
{
  messages: Array<{ role: 'user' | 'assistant'; content: string; citations?: string[] }>;
  isStreaming: boolean;
  context: { page: string; entityId?: string };  // Auto-set by page components
  sendMessage: (text: string) => Promise<void>;
  clearHistory: () => void;
  setContext: (ctx) => void;
}
```

### `useCanvasStore`
```ts
{
  activeCanvasId: string | null;
  aiSuggestEnabled: boolean;
  selectedNodeIds: string[];
  viewFilter: 'all' | 'documents' | 'concepts' | 'zettels';
  setActiveCanvas: (id: string) => void;
  toggleAiSuggest: () => void;
  setViewFilter: (f) => void;
  selectNodes: (ids: string[]) => void;
}
```

Existing Zustand stores are preserved as-is.

## 9. Error, Loading, and Empty States

### Loading States
- **Inbox stream:** Skeleton cards (3-4 shimmer placeholders) during initial load.
- **Canvas:** Centered spinner with "Loading canvas..." text.
- **Dashboard cards:** Individual skeleton loaders per card (metrics load independently).
- **AI panel:** Typing indicator (three-dot animation) during streaming.

### Empty States
- **Inbox (no documents):** Illustration + "Your knowledge inbox is empty. Connect a source or paste a URL to get started." + [Connect Sources] button.
- **Canvas (no nodes):** Empty canvas with ghost text: "Drag items from your Inbox, or click + to create a note."
- **Dashboard (no data):** Cards show "Not enough data yet" with a link to the Inbox.
- **AI panel (no history):** Prompt suggestions: "Try asking: What do I know about...", "Summarize my recent readings", "Find connections between..."

### Error States
- **API failure:** Toast notification with error message + retry button. Content area shows last successful data (stale-while-revalidate via TanStack Query).
- **AI panel error:** Inline error message in chat with [Retry] button.
- **Canvas save failure:** Auto-retry with exponential backoff (3 attempts). If all fail, show warning banner: "Changes not saved. Retrying..."

## 10. Route Structure (New)

```
app/
  layout.tsx                     # Root layout (providers, fonts)
  providers.tsx                  # TanStack Query, theme, Clerk
  page.tsx                       # Redirect to /inbox
  sign-in/                       # Clerk (kept)
  sign-up/                       # Clerk (kept)
  not-found.tsx                  # 404 (kept)
  api/                           # Next.js API routes (kept)
  (app)/
    layout.tsx                   # New app shell (top bar, AI panel slot, tool panel slot)
    _components/
      app-shell.tsx              # New shell component
      top-bar.tsx                # New top navigation bar
      ai-panel.tsx               # Persistent AI panel (Cmd-J)
      tool-panel.tsx             # Generic slide-over panel container
    inbox/
      page.tsx                   # Knowledge Inbox (home)
      _components/
        inbox-stream.tsx         # Unified stream with infinite scroll
        inbox-filters.tsx        # Source tabs + filter bar
        inbox-item.tsx           # Single stream item card
        inbox-detail.tsx         # Expanded item detail view
    canvas/
      page.tsx                   # Default canvas (redirects to most recent)
      [canvasId]/
        page.tsx                 # Specific canvas
      _components/
        canvas-workspace.tsx     # @xyflow/react canvas container
        canvas-toolbar.tsx       # Top toolbar (zoom, grid, AI suggest toggle)
        canvas-selector.tsx      # Canvas picker (bottom bar dropdown)
        canvas-node-document.tsx # Custom node: document
        canvas-node-concept.tsx  # Custom node: concept
        canvas-node-zettel.tsx   # Custom node: zettel with mini-editor
        canvas-edge.tsx          # Custom edge (solid + dashed AI-suggested)
    dashboard/
      page.tsx                   # Dashboard
      _components/
        knowledge-score.tsx      # Hero score display
        retention-card.tsx       # Retention metrics + decay chart
        coverage-card.tsx        # Topic heatmap
        connections-card.tsx     # Graph metrics + mini preview
        activity-strip.tsx       # 7-day sparkline
  (canvas)/
    system-design/               # Kept as-is (full-screen Excalidraw)
```
