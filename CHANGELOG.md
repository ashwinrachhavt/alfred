# Changelog

All notable changes will be documented in this file. Follow Keep a Changelog style; versions are date-stamped until releases are tagged.

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
