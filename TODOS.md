# TODOS

## P1 — Blocking

### Unify Retrieval: Qdrant for Both Documents and Zettels
**What:** Index zettel embeddings in Qdrant instead of Postgres JSON + in-process cosine scoring. Give `search_kb` one unified vector search path.
**Why:** Document chunks are in Qdrant but zettel embeddings are in Postgres JSON with in-process scoring. Two retrieval systems means no unified ranking for push retrieval and related cards.
**How to start:** Create a `zettels` collection in Qdrant. Write a migration script to embed and index all existing zettels. Update `search_kb` tool to query both collections with unified scoring. Remove in-process cosine from zettelkasten_service.py.
**Depends on:** Qdrant Cloud access
**Added:** 2026-03-28

---

## P2 — Important

### Daily Collision: Cross-Domain Semantic Surfacing
**What:** Scheduled Celery job that takes two zettels from different domains with high embedding similarity and presents them side-by-side.
**Why:** Forces cross-domain thinking — the resonance between seemingly unrelated topics is where real insight lives.
**How to start:** After KB has 50+ zettels across 3+ domains, create a Celery beat task that runs daily. Query Qdrant for high cross-domain similarity pairs. Present in the agent chat as a "Daily Collision" card.
**Depends on:** Unified Qdrant retrieval + KB depth (50+ zettels, 3+ domains)
**Added:** 2026-03-28

### ReviewStation: Use Real Data
**What:** Fix ReviewStation component to use real zettel data from `useZettelCards()` instead of `MOCK_ZETTELS`.
**Why:** Review section shows 12 fake philosophy zettels while cards/table/graph show real data.
**How to start:** In `knowledge-hub.tsx`, change `<ReviewStation zettels={MOCK_ZETTELS} />` to `<ReviewStation zettels={allZettels} />`. Update review components to handle empty arrays.
**Added:** 2026-03-29

### Integration Tests for Enrichment Pipeline
**What:** Add integration tests for `_create_zettel_from_enrichment()` in `document_enrichment.py` with mocked LLM responses. Cover: happy path (multi-card), fallback (single card), skip (already exists), no-content.
**Why:** This function is the critical Inbox → Knowledge Hub bridge. Currently 0% tested.
**How to start:** Create `tests/alfred/tasks/test_document_enrichment.py`. Mock `get_chat_model()`.
**Added:** 2026-03-29

### Extract Celery-Safe Session Helper
**What:** Create `apps/alfred/core/celery_db.py` with a `@contextmanager celery_session()` replacing bare `next(get_db_session())` + manual close.
**Why:** Current pattern bypasses FastAPI's dependency injection cleanup logic.
**Added:** 2026-03-29

### Chunked Decomposition for Long Articles
**What:** The zettel decomposer truncates article text to 8000 chars. For articles over 8K, later sections are invisible to the LLM.
**Why:** Long articles lose 60%+ of content. Key insights in later sections are lost.
**How to start:** Implement map-reduce decomposition: chunk into 8K segments, decompose each, deduplicate. Or increase limit to 16-32K (GPT-5.4 supports 128K context).
**Added:** 2026-03-29

### Excalidraw AI: Switch to Mermaid Pipeline
**What:** Change canvas AI from raw Excalidraw JSON generation to LLM → Mermaid → Excalidraw conversion.
**Why:** Mermaid is simpler and LLMs handle it more reliably. The repo already has `parseMermaidToExcalidraw`.
**How to start:** Change `build_diagram_prompt()` to request Mermaid output. Convert via existing parser. Remove `auto_layout()`.
**Added:** 2026-03-29

### Landing Page CTAs (Clerk Auth Disabled)
**What:** "Begin Thinking" and "Create account" buttons don't work because Clerk keys are expired.
**How to start:** Either refresh Clerk keys, or remove the env var to fall back to non-Clerk path.
**Added:** 2026-03-29

---

## P3 — Nice to Have

### Add Anthropic Provider to llm_factory.py
**What:** Implement the `anthropic` case in `get_chat_model()` using `langchain-anthropic`.
**Why:** Enables Claude models for the agent.
**How to start:** Add `anthropic` to `LLMProvider` enum, implement in `llm_factory.py`.
**Added:** 2026-03-28

### Adaptive Engagement Threshold
**What:** Replace the fixed score-40 auto-capture threshold with one that learns from user behavior.
**Why:** Fixed threshold doesn't account for different reading styles.
**How to start:** After 2 weeks of engagement data, analyze score distributions.
**Depends on:** Smart Reader v1 live
**Added:** 2026-03-27

### Fix "Ozempicization" Zettel
**What:** This zettel has a SQLAlchemy error log as its summary instead of article content.
**Why:** Enrichment pipeline captured an API error response.
**How to start:** Re-run enrichment or manually edit. Root cause: add error detection in enrichment pipeline.
**Added:** 2026-03-29
