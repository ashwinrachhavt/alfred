# Changelog

All notable changes will be documented in this file. Follow Keep a Changelog style; versions are date-stamped until releases are tagged.

## [0.1.0.0] - 2026-04-12 — Interactive Learning: Daily Review Deck

### Added
- **Daily review deck**: ReviewStation now fetches real review data from the spaced repetition system. Open Knowledge > Review to complete today's cards with self-grading (Forgot / Partial / Nailed it) and keyboard shortcuts (Space / 1 / 2 / 3).
- **Aggregate daily-deck endpoint**: `GET /api/learning/daily-deck` returns reviews, topics, quiz items, and source provenance in a single call, avoiding N+1 request waterfalls.
- **Source provenance on review cards**: every question shows which document it came from and when it was captured, so you can verify answers against original sources.
- **Session summary**: after completing a deck, see recall percentage, weak topics, and how many items are due tomorrow.
- **Sidebar "Review" entry**: Brain icon in the Discover section for quick access to the daily review.
- **Spaced repetition tests**: 4 dedicated tests covering all branches of `compute_next_review_schedule` (pass, pass-at-max, fail, null-score).
- **Review safety guards**: guard clause prevents double-grading from stale tabs; quiz generation is now idempotent (returns existing quiz on retry instead of creating duplicates).

### Changed
- **Design system fonts**: layout.tsx and globals.css now wire Source Serif 4 (display), DM Sans (body/UI), and JetBrains Mono (data/system) per DESIGN.md specification. Replaces Inter + Instrument Serif + Geist.
- **ReviewStation default mode**: switches from mock-data flashcards to the real Daily Review backed by the daily-deck API.

## [0.0.3.0] - 2026-04-11 — Planner-Driven Agent Orchestration

### Added
- **Planner-driven orchestrator**: Alfred's agent now uses a multi-step planner (planner -> tasks -> writer) instead of a flat tool loop. The planner breaks complex requests into parallel tasks routed to specialist workers (knowledge, research, synthesis).
- **SSE streaming for orchestrator events**: The `/api/agent/stream` endpoint now emits plan, task_start, task_done, approval_required, and phase events so the frontend can show real-time orchestration progress.
- **Orchestrator workers**: Knowledge and synthesis teams execute as worker subgraphs with their own tool sets, results gathered and optionally gated by an approval step.
- **New orchestrator nodes**: planner, direct_chat, execute_task, gather_results, approval_gate, writer, finalizer.
- **Frontend chat components**: MessageBubble component and updated agent store for orchestrator event handling.

### Changed
- Agent routes switched from `AgentService` (flat OpenAI loop) to `build_alfred_graph()` (LangGraph orchestrator) for all streaming.
- Agent store refactored to handle new SSE event types (plan, task_start, task_done, phase).
- Teams (knowledge, ingest, synthesis) simplified to worker callables for orchestrator dispatch.

### Removed
- Stopped tracking `docs/superpowers/` directory (large generated plan/spec files removed from git).
- Removed 4,600+ lines of stale plan and spec documents.

## [0.0.2.0] - 2026-04-05 — Tech Debt Cleanup + Performance

### Removed
- Dead code from job-search pivot: question extraction utils, taxonomy canonicalizer, deep_research shims, 9 unused interview/company settings, deprecated aliases (CompanyResearchReportRow, DeepResearch*)
- 5 unused Python deps: lancedb, tinydb, duckduckgo-search, chromadb, langchain-chroma
- Unused frontend hooks (useNowMs, useTaskPolling), dead snooze/due-date utils
- Stale test files for removed code

### Performance
- React.memo on ZettelCard and InboxItem list components
- DRY query filter extraction in zettelkasten_service (`_apply_card_filters`)
- Single JSON containment check for tag filtering (was per-tag loop)
- Redis caching (5min TTL) on /topics and /tags endpoints with invalidation on mutations
- 3 new DB indexes on zettel_cards: status, document_id, updated_at
- next.config: optimizePackageImports for lucide-react/radix-ui/date-fns, removeConsole in prod

### Changed
- Rewrote all project documentation (CLAUDE.md, README.md, AGENTS.md, TODOS.md) for accurate AI-assisted coding
- Removed `docs/` from .gitignore so documentation can be version-controlled
- Fixed .gitignore typo (stray 's' line)
- Deduplicated TODOS.md (Chunked Decomposition and Excalidraw AI were each listed twice)

## [0.0.1.0] - 2026-04-04 — MCP Server + Design Overhaul

### Added
- **Alfred MCP Server**: Claude Code can now access Alfred's knowledge base via MCP. 5 tools: search_knowledge (keyword), get_zettel, get_document, get_related, save_insight. Stdio transport, auto-logging to ~/.alfred/mcp-sessions.jsonl
- **12 unit tests** for MCP tools (SQLite in-memory with StaticPool)

### Changed
- **Design system overhaul**: Midnight Editorial direction. Source Serif 4 (display), DM Sans (body), Berkeley Mono (system). Deep orange accent (#E8590C) on warm charcoal (#0F0E0D). Sharp corners, editorial density
- Updated CLAUDE.md with skill routing rules and design system quick reference

### Removed
- Stale plan files from docs/superpowers/ and .claude/docs/

## 2026-03-31 — Product Quality Pass

### Added
- **Real AI agent**: OpenAI streaming with tool calling (search_kb, create/get/update zettel), 5-round tool loop, reasoning traces for o3/o4 models
- **UnifiedChat**: single chat component with sidebar (380px) and expanded (full-width) modes, replacing the split AI panel + agent page
- **Bulk zettel creation**: POST /api/zettels/cards/bulk endpoint (max 50), bulk create dialog on Knowledge hub
- **Workflow triggers**: Bulk Enrich and Reclassify buttons on Knowledge hub toolbar with background task tracking
- **Notification center**: bell icon with active task badge, persistent task drawer with auto-purge (24h)
- **Command palette extensions**: create zettel, create note, trigger workflows, search zettels via Cmd+K
- **Optimistic zettel creation**: instant card appearance with shimmer, revert on API error
- **Pipeline progress**: step-by-step enrichment status (Enriching/Creating zettels/Finalizing)
- **Loading skeletons**: route-level loading states for Knowledge and Connectors pages
- **Reasoning traces**: collapsible "Thinking..." section for o3/o4 model responses in chat

### Changed
- Token buffer flush interval from 50ms to 100ms for smoother streaming
- Tool call matching now uses call_id instead of array position (supports multi-round)
- Agent store normalized to messagesById/messageOrder map (from flat array)

### Fixed
- SSE parser chunk splitting: events no longer silently dropped when event/data arrive in different TCP chunks
- Agent tool signatures: create_zettel and update_zettel now correctly call ZettelkastenService APIs
- N+1 queries in document enrichment and zettel bulk update
- LLM calls now have 30s timeout (were unbounded)
- CSS grain overlay GPU-promoted, respects prefers-reduced-motion

### Performance
- GZip middleware for API response compression
- Dynamic import Three.js and TipTap editor (saves ~500KB initial bundle)
- Zustand useShallow selectors on all store consumers
- React.memo + useCallback on MessageBubble, PanelMessage, ReportListItem
- Redis version-key cache for semantic map (eliminates redundant DB queries)
- Celery group() for parallel batch image generation
- Database index on documents.pipeline_status
- Standardized React Query staleTime across all query hooks
- Route prefetching on sidebar navigation links

## 2025-12-23

- Fixed interview sync persistence when using the Postgres-backed ProxyCollection by implementing `bulk_write` and `$setOnInsert` handling in the Mongo emulation layer.
- Added outreach persistence to Postgres (`outreach_runs`, `outreach_contacts`) and migrated database accordingly.
- Enabled Alembic autogenerate flow: `scripts/alembic_autogen.sh` and `make alembic-autogen` / `make alembic-upgrade` with `PYTHONPATH=apps` + `DATABASE_URL`.
- Clarified database docs in README for Postgres + autogen usage.

## 2025-12-22

- Contact discovery resiliency: Apollo falls back to mixed_people/search + organization_top_people; caching preserved.

## 2025-12-21

- Initial migrations and schema (research, learning, zettelkasten).
