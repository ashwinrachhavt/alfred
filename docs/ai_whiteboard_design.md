# AI Whiteboard with Excalidraw + Postgres

## Purpose and goals
- Add a collaborative diagramming surface that can capture structured knowledge (concept maps, workflows, schemas) and connect it to Alfred data sources.
- Provide generative helpers to draft, clean up, and summarize whiteboards so teams can move from rough ideas to production-ready diagrams quickly.
- Persist boards, revisions, and AI context in Postgres to keep data queryable, auditable, and portable.

## User stories
- As a researcher, I can start a blank canvas or a template, ask the AI to "lay out a multi-agent pipeline for collecting market signals", and get an editable diagram.
- As a builder, I can drag/drop shapes, freehand sketch, or import an existing Excalidraw file, and Alfred stores every version with comments.
- As a teammate, I can co-edit in real time, see cursors, and ask the AI to summarize the board or generate next-step tasks.
- As a platform admin, I can export a board (JSON/PNG/SVG) or sync its structured nodes/edges into other Alfred workflows.

## Solution options
### Option A: Embed open-source Excalidraw (default path)
- Use the Excalidraw React component within the existing UI shell.
- Extend with custom panels for: AI prompts, database-linked shapes, and export actions.
- Persist the Excalidraw scene JSON plus Alfred metadata into Postgres; keep compatibility with Excalidraw import/export.
- Pros: mature UX, battle-tested interactions, ecosystem plugins. Cons: constrained rendering pipeline for exotic AI overlays.

### Option B: Custom canvas with generative-first primitives (fallback)
- Build a minimal canvas (Konva/FabricJS) with shape primitives and path tools, wrapping them in CRDT-friendly structures.
- Gives full control for AI overlays (e.g., heatmaps, inline suggestions), but higher build/test cost.

Recommendation: start with Option A to ship quickly; keep interfaces (storage schema, collaboration protocol, AI services) framework-agnostic so we can swap the renderer later.

## Architecture
- **Client**: React page embedding Excalidraw, plus side panels for AI prompt composer and board metadata. Uses WebSockets for live cursors and CRDT/OT sync.
- **API (FastAPI)**: CRUD endpoints for boards, revisions, comments, exports; WebSocket endpoint for collaboration; background tasks for heavy AI/exports via Celery.
- **AI services**: Prompt-to-diagram generator, autolayout/refinement, board summarizer, and task extractor. Runs via existing LLM orchestration (LangChain/LangGraph) and queues.
- **Storage (Postgres)**: JSONB for scenes, normalized tables for boards/elements/revisions, and vector/metadata fields for AI context. Optional blob store (S3/GCS) for attachments.

## Data model (Postgres)
- `whiteboards(id, title, created_by, org_id, template_id, is_archived, created_at, updated_at)`
- `whiteboard_revisions(id, whiteboard_id, revision_no, scene_json jsonb, ai_context jsonb, applied_prompt, created_by, created_at)`
- `whiteboard_elements(id, whiteboard_id, revision_id, element_type, props jsonb, position geometry, z_index, data jsonb, created_at)` — optional for querying nodes/edges individually.
- `whiteboard_comments(id, whiteboard_id, element_id, body, author_id, resolved, created_at)`
- `whiteboard_links(id, whiteboard_id, target_type, target_id, metadata jsonb)` to link shapes to Alfred entities (documents, tasks, datasets).
- Indexing: GIN on `scene_json`, partial indexes on active boards, and `btree` on `whiteboard_id + revision_no` for fast latest revision lookup.
- Auditing: triggers to snapshot diffs between revisions; soft deletes via `is_archived` to preserve history.

## API and collaboration
- REST endpoints
  - `POST /whiteboards` create from blank/template/import; optionally accepts Excalidraw scene.
  - `GET /whiteboards/{id}` fetch latest revision; `GET /whiteboards/{id}/revisions` for history.
  - `POST /whiteboards/{id}/revisions` save a new revision; optional `applied_prompt` and AI outputs.
  - `POST /whiteboards/{id}/comments` and `PATCH /comments/{id}`.
  - `POST /whiteboards/{id}/export` -> PNG/SVG/JSON; queued if large.
- Collaboration
  - WebSocket channel `/ws/whiteboards/{id}` using CRDT (Yjs/Automerge) payloads so multiple clients merge changes safely.
  - Presence updates (cursors, selection), throttled to reduce traffic.
  - Server persists periodic checkpoints to `whiteboard_revisions`; clients can request the last stable snapshot after reconnect.

## Generative AI experiences
- **Prompt-to-diagram**: take a natural-language prompt, generate a graph (nodes, edges, labels) using LLM + domain schemas, then map to Excalidraw primitives and apply autolayout.
- **Context-aware suggestions**: when a shape is selected, show inline AI hints (add missing step, suggest API call, generate sample data) using nearby elements + linked Alfred resources.
- **Summarize & actionize**: summarize the board, extract tasks, and publish them into Alfred task queues.
- **Data import/export**: ingest external schemas or workflow configs and render them; export structured JSON for downstream automation.
- **Safety**: guardrails for model outputs (type-safe graph schema, max node/edge counts, profanity filters) before rendering.

## Operational concerns
- **Performance**: compress WebSocket payloads, debounce edits, and chunk large scenes. Offload heavy exports and AI jobs to Celery workers.
- **Security & auth**: reuse existing JWT/session, enforce org/team scoping on every endpoint, and validate that AI-generated links target resources the user can access.
- **Backups & retention**: daily backups of Postgres; object storage lifecycle rules for attachments; optional purge of archived boards after N days.
- **Observability**: metrics on AI latency, collaboration reconnects, and revision size; structured logs for AI prompts/responses tied to revision IDs.

## Iterative rollout
1. **MVP**: Excalidraw embed with board CRUD, revision saves, and manual export; single-user edits persist to Postgres.
2. **Collaboration**: add WebSocket + CRDT sync, cursors, and comments.
3. **Generative**: prompt-to-diagram and summarizer, with guardrails and undoable revisions.
4. **Integrations**: linking shapes to Alfred resources, task creation from boards, and scheduled exports.
5. **Polish**: autolayout refinement, templates gallery, keyboard shortcuts, and analytics dashboards.

## Excalidraw integration path
- **UI embed**: use the [`@excalidraw/excalidraw`](https://www.npmjs.com/package/@excalidraw/excalidraw) React component inside the existing Alfred shell. Provide `initialData` from `GET /api/whiteboards/{id}` (latest `scene_json`), and wrap `onChange` with debounce to call `POST /api/whiteboards/{id}/revisions` so we persist every save as a revision.
- **Auth + scoping**: reuse the current session/JWT headers for API calls; pass `org_id`/`created_by` in the payloads so the backend enforces tenancy and authorship already modeled in `Whiteboard` rows.
- **Comments + metadata**: map Excalidraw element IDs to comment threads by calling `POST /api/whiteboards/{id}/comments` with `element_id`; update board titles/descriptions with `PATCH /api/whiteboards/{id}` to keep UI metadata in sync.
- **Real-time layer**: start with single-user persistence; when collaboration is enabled, mirror Excalidraw updates through a Yjs provider on `/ws/whiteboards/{id}` and checkpoint snapshots to `whiteboard_revisions` on an interval.
- **Import/export**: allow users to import `.excalidraw` files by pushing the parsed scene JSON into `POST /api/whiteboards` (creates board + first revision). For exports, reuse Excalidraw’s `exportToSvg/exportToBlob` client helpers or call the server-side export endpoint when assets are large.
- **Generative hooks**: surface an “AI” dock next to the canvas that sends prompts to the AI service; when a response returns a new graph layout, translate it to Excalidraw shapes and commit it as a new revision so undo/history stay coherent.
