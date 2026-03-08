# System Design v2 — Technical design (engine + state + sync)

## Summary

System Design v2 should be a **structured diagram editor** (components + connections), with:
- A renderer that feels like a professional architecture tool (not a freehand whiteboard)
- A canonical diagram state model that is **renderer-agnostic**
- Persistence with optimistic concurrency (`version`)
- A realtime channel designed for eventual **CRDT-based** collaboration (Yjs)

**Recommendation:** introduce a new canonical schema (`DiagramV2`) and render it with a node/edge engine (React Flow / `@xyflow/react`). Keep the current Excalidraw-based editor as **legacy/freeform**, and provide an explicit “Upgrade to v2” migration path.

---

## Current state (in repo)

- Frontend System Design editor uses **Excalidraw** (`web/components/system-design/excalidraw-canvas.tsx`).
- Sessions persist to Postgres via `DataStoreService` as JSON documents (`apps/alfred/services/system_design.py`).
- Realtime currently exists as a **broadcast-only WebSocket** (`/api/system-design/sessions/{session_id}/ws`) with optional autosave on messages (`apps/alfred/api/system_design/routes.py`).

This is strong for “whiteboard + AI”, but it is not a great foundation for:
- Ports/handles, smart connectors, and routable edges
- Deterministic auto-layout
- Reliable export to Mermaid/PlantUML as structured code
- Conflict-free multi-user editing

---

## Goals / Non-goals

### Goals
- Canonical diagram state: `components[]`, `connections[]`, `viewport`, `version`
- Deterministic editing operations (add/move/update/delete components & connections)
- Exportable representation (Mermaid/PlantUML) without lossy parsing of freehand shapes
- Realtime protocol that supports presence + cursor broadcasting immediately and CRDT later

### Non-goals (v1 of v2)
- Full “freehand drawing” parity with Excalidraw
- Pixel-perfect import fidelity from arbitrary Excalidraw files
- Multi-canvas/multi-page diagrams (can be layered later)

---

## Renderer / engine decision

### Option A — Continue with Excalidraw (status quo)
**Pros**
- Already integrated and stable
- Great UX for freehand / sketching

**Cons**
- Diagram semantics (ports, connectors, auto-layout) are difficult and brittle
- Export to code formats is inherently lossy unless we constrain allowed shapes heavily
- Collaboration at scale typically requires adopting Excalidraw’s collab stack or building a parallel CRDT layer

### Option B — Node/edge engine: React Flow (`@xyflow/react`) (recommended)
**Pros**
- Built for structured components + connections (handles/ports, edge routing, selection)
- Plays well with a canonical node/edge schema and deterministic operations
- Auto-layout integration is straightforward (ELK/Dagre produce node positions)
- Exports to Mermaid/PlantUML become direct transforms of the state model

**Cons**
- New dependency + new editor surface (migration work)
- DOM-based rendering can degrade for extremely large graphs (but 100–300 nodes is well within typical budgets)

### Option C — Custom canvas (Konva/Fabric/WebGL)
**Pros**
- Maximum control over rendering and perf
- Clean path to “design-tool grade” visuals and interactions

**Cons**
- High build cost: selection model, snapping, hit-testing, connectors, text editing, accessibility
- Harder to iterate quickly and ship features

### Decision
Adopt **Option B** for the structured editor, and treat Excalidraw as:
- Legacy format for existing sessions
- A freeform “scratchpad” mode (optional, future)

---

## Canonical diagram state model (DiagramV2)

### Principles
- **Renderer-agnostic**: the stored model should not depend on React Flow or any canvas library
- **Stable IDs**: components and connections have stable IDs (UUID/ULID)
- **Explicit ports**: connections attach to ports (even if most components use defaults)
- **Optimistic concurrency**: server increments `version` on update, clients send `baseVersion`

### JSON schema (v1)

```json
{
  "schemaVersion": 1,
  "version": 12,
  "viewport": { "x": 120, "y": -80, "zoom": 1.0 },
  "components": [
    {
      "id": "cmp_01J...X",
      "type": "service",
      "label": "API Service",
      "position": { "x": 560, "y": 320 },
      "size": { "w": 240, "h": 120 },
      "ports": [
        { "id": "in", "side": "left", "label": "HTTP" },
        { "id": "out", "side": "right", "label": "SQL" }
      ],
      "metadata": { "tags": ["stateless"] }
    }
  ],
  "connections": [
    {
      "id": "con_01J...A",
      "source": { "componentId": "cmp_01J...X", "portId": "out" },
      "target": { "componentId": "cmp_01J...Y", "portId": "in" },
      "label": "queries",
      "metadata": { "protocol": "postgres" }
    }
  ],
  "metadata": { "title": "System design" }
}
```

### Notes
- Coordinate system uses “world pixels” with `(0,0)` in the top-left of the canvas space.
- `viewport.x/y` represent pan offsets in world space; `zoom` is a scalar (0.1–4.0).
- `type` is aligned to the component library (`client`, `service`, `database`, etc.).

---

## Persistence + versioning

### Storage (server)
Extend the session document to support multiple diagram formats:

```json
{
  "diagram_format": "excalidraw" | "v2",
  "diagram": { /* existing ExcalidrawData */ },
  "diagram_v2": { /* DiagramV2 */ },
  "diagram_version": 12
}
```

- `diagram_version` is authoritative for optimistic concurrency.
- Keep the existing `versions[]` history for now, but add a retention cap (e.g. last 50 snapshots) or migrate to a dedicated history table later.

### API endpoints (CRUD)
Maintain the existing session surface area, but make it explicitly satisfy diagram CRUD:

- `POST /api/system-design/sessions` — create a new session (optionally from template)
- `GET /api/system-design/sessions/{sessionId}` — load session + current diagram (format-aware)
- `PATCH /api/system-design/sessions/{sessionId}/diagram` — update diagram (requires `baseVersion`)
- `GET /api/system-design/sessions` — list sessions (new; cursor + limit)

**Update payload (v2)**

```json
{
  "format": "v2",
  "baseVersion": 12,
  "diagram": { /* DiagramV2 */ }
}
```

Server behavior:
- If `baseVersion != diagram_version`, return `409 Conflict` with the latest `diagram_version`.
- On success: persist, increment `diagram_version`, and return the updated session.

---

## Realtime collaboration: channel semantics

### Immediate (presence + cursors, no CRDT)
Reuse the existing WebSocket route:

- `WS /api/system-design/sessions/{sessionId}/ws`

Message types (JSON):
- `presence.join` / `presence.leave` — user joined/left (avatar/name)
- `cursor.update` — `{ x, y, selectionIds[] }` throttled (~10/sec)
- `diagram.updated` — broadcasted only after successful REST save (watchers update their view)

This supports “one active editor + many viewers” without conflict resolution.

### CRDT-ready (multi-editor)
Introduce CRDT operations without breaking the URL:

- `crdt.update` — Yjs binary updates (base64 in JSON, or switch to binary frames)
- `crdt.snapshot.request` / `crdt.snapshot.response` — for fast resync after reconnect

Server responsibilities (v1):
- Relay CRDT updates between connected clients
- Periodically checkpoint the canonical `DiagramV2` snapshot to persistence

Rationale for CRDT (Yjs):
- Proven ecosystem, small incremental updates, built-in “awareness” for presence
- Keeps clients responsive even with intermittent connectivity

---

## Performance strategy

- **State management**: use a normalized store (e.g. Zustand) keyed by component/connection ID; avoid “replace whole diagram” renders.
- **Drag perf**: update positions in-memory during drag; persist on mouse-up (or debounce).
- **LOD rendering**: when zoomed out, hide labels/ports; reduce DOM complexity.
- **Throttling**: cursor/selection updates capped at ~10/sec; autosave at ~30s.
- **Layout**: run auto-layout in a worker where possible; apply positions as a single batched update.

---

## Migration strategy (Excalidraw → v2)

Migration should be explicit and reversible:

1. Add `diagram_format` field; existing sessions default to `excalidraw`.
2. Add an “Upgrade to v2” action:
   - Attempt to convert: rectangles with labels → `components`, arrows/lines with bindings → `connections`.
   - Preserve the original Excalidraw payload in `metadata.legacy_excalidraw` (or keep `diagram` alongside `diagram_v2`).
3. If conversion confidence is low (e.g. too many unbound arrows), prompt the user to start fresh in v2.

---

## Key risks + mitigations

- **Migration lossiness:** constrain conversion to simple shapes; keep legacy payload for rollback.
- **Collaboration complexity:** ship presence + viewer sync first; adopt Yjs updates behind a feature flag.
- **Export correctness:** build exports from `DiagramV2` only; treat freeform drawings as non-exportable.
- **Performance regressions:** cap supported node count for v1 (e.g. 300) and add profiling fixtures early.

