# Alfred Performance Optimization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate 25+ performance bottlenecks across backend and frontend, making Alfred noticeably snappier for all user flows.

**Architecture:** Three-phase "Foundation + Flows + Polish" approach. Phase 1 fixes systemic issues (indexes, store patterns, bundle splits). Phase 2 optimizes specific hot paths (agent streaming, document pipeline, navigation). Phase 3 polishes (CSS paint, cache tuning, compression).

**Tech Stack:** FastAPI, Celery, Redis, PostgreSQL/SQLModel/Alembic, Next.js 16, React 19, Zustand, TanStack React Query, Tailwind CSS 4

**Spec:** `docs/superpowers/specs/2026-03-29-performance-optimization-design.md`

---

## File Structure

### Backend — New Files
- `apps/alfred/migrations/versions/xxxx_add_pipeline_status_index.py` — Alembic migration for missing index
- `apps/alfred/api/tasks_status.py` — Shared async task polling endpoint (`GET /api/tasks/{task_id}`)
- `apps/alfred/tasks/planning.py` — Celery task for async plan generation

### Backend — Modified Files
- `apps/alfred/models/doc_storage.py` — Add index to `__table_args__`
- `apps/alfred/tasks/document_enrichment.py` — Fix N+1 query in `_create_zettel_from_enrichment()`
- `apps/alfred/api/zettels/routes.py` — Fix N+1 in `bulk_update_cards()`
- `apps/alfred/services/llm_service.py` — Add `timeout=30` to OpenAI calls
- `apps/alfred/core/llm_factory.py` — Remove temperature from cache key
- `apps/alfred/api/documents/routes.py` — Move scraping + image gen to Celery, reduce semantic map limit
- `apps/alfred/api/intelligence/routes.py` — Convert planning endpoint to async with task polling
- `apps/alfred/tasks/document_title_image.py` — Use `celery.group()` for batch dispatch
- `apps/alfred/tasks/document_processing.py` — Add fetch_organize_task
- `apps/alfred/services/doc_storage/_semantic_map_mixin.py` — Redis version-key cache invalidation
- `apps/alfred/core/celery.py` — Register new task modules
- `apps/alfred/api/app.py` — Mount new tasks_status router, add GZip middleware

### Frontend — New Files
- `web/hooks/use-task-polling.ts` — Shared hook for polling Celery task status
- `web/app/(app)/dashboard/loading.tsx` — Dashboard skeleton
- `web/app/(app)/documents/loading.tsx` — Documents skeleton
- `web/app/(app)/research/loading.tsx` — Research skeleton
- `web/app/(app)/agent/loading.tsx` — Agent skeleton
- `web/app/(app)/notes/loading.tsx` — Notes skeleton

### Frontend — Modified Files
- `web/lib/stores/agent-store.ts` — Normalize messages to indexed map, isolate tool calls, increase flush interval
- `web/app/(app)/agent/_components/agent-chat-client.tsx` — Add selectors, memoize MessageBubble + callbacks
- `web/app/(app)/_components/ai-panel.tsx` — Add selectors, cache threads, memoize PanelMessage
- `web/app/(app)/research/_components/research-client.tsx` — Memoize ReportListItem + callbacks
- `web/features/documents/queries.ts` — Fix staleTime values
- `web/app/globals.css` — GPU-promote grain overlay, respect prefers-reduced-motion

### Frontend — Dynamic Import Wrappers
- Components importing Three.js/react-three — wrap with `next/dynamic`
- Components importing TipTap — wrap with `next/dynamic`

---

## Phase 1: Foundation

### Task 1: Add pipeline_status Database Index

**Files:**
- Modify: `apps/alfred/models/doc_storage.py:141-148`
- Create: `apps/alfred/migrations/versions/xxxx_add_pipeline_status_index.py`

- [ ] **Step 1: Add index to model `__table_args__`**

In `apps/alfred/models/doc_storage.py`, add the index to the existing tuple:

```python
__table_args__ = (
    sa.Index("ix_documents_hash", "hash", unique=True),
    sa.Index("ix_documents_captured_at_desc", "captured_at"),
    sa.Index("ix_documents_day_bucket", "day_bucket"),
    sa.Index("ix_documents_topics", "topics", postgresql_using="gin"),
    sa.Index("ix_documents_metadata", "metadata", postgresql_using="gin"),
    sa.Index("ix_documents_tags", "tags", postgresql_using="gin"),
    sa.Index("ix_documents_pipeline_status", "pipeline_status"),
)
```

- [ ] **Step 2: Generate Alembic migration**

Run: `cd apps/alfred && alembic revision --autogenerate -m "add pipeline_status index"`

Expected: New migration file in `apps/alfred/migrations/versions/`

- [ ] **Step 3: Review and apply migration**

Read the generated migration to verify it only contains `CREATE INDEX`. Then run:
`cd apps/alfred && alembic upgrade head`

Expected: Migration applies successfully.

- [ ] **Step 4: Commit**

```
git add apps/alfred/models/doc_storage.py apps/alfred/migrations/versions/
git commit -m "perf(db): add index on documents.pipeline_status"
```

---

### Task 2: Fix N+1 Query in Document Enrichment

**Files:**
- Modify: `apps/alfred/tasks/document_enrichment.py:65-73`

- [ ] **Step 1: Read zettelkasten_service to find the right query method**

Check `apps/alfred/services/zettelkasten_service.py` for how to query by `document_id`. We need to know the model and available methods. Look for `get_card`, `list_cards`, and the underlying SQLModel.

- [ ] **Step 2: Replace the N+1 pattern with a direct query**

In `apps/alfred/tasks/document_enrichment.py`, replace lines 65-73:

```python
# OLD (loads 1000 cards and searches linearly):
# existing = zk.list_cards(q=None, topic=None, limit=1000)
# for card in existing:
#     if getattr(card, "document_id", None) == doc_id:
#         ...

# NEW (direct database query):
from sqlmodel import select
from alfred.models.zettelkasten import ZettelCardRow

existing = session.exec(
    select(ZettelCardRow).where(ZettelCardRow.document_id == doc_id).limit(1)
).first()
if existing:
    logger.info("Zettel already exists for document %s", doc_id)
    return str(existing.id)
```

- [ ] **Step 3: Verify the fix runs correctly**

Run the enrichment task manually or via test to ensure it correctly detects existing zettels and creates new ones. Check that the `ZettelCardRow` model has a `document_id` column:

`cd apps/alfred && python -c "from alfred.models.zettelkasten import ZettelCardRow; print([c.name for c in ZettelCardRow.__table__.columns if 'document' in c.name])"`

Expected: Output includes `document_id`.

- [ ] **Step 4: Commit**

```
git add apps/alfred/tasks/document_enrichment.py
git commit -m "perf(enrichment): replace N+1 zettel lookup with direct document_id query"
```

---

### Task 3: Fix N+1 Query in Zettel Bulk Update

**Files:**
- Modify: `apps/alfred/api/zettels/routes.py:78-97`

- [ ] **Step 1: Replace per-item get_card with batch fetch**

In `apps/alfred/api/zettels/routes.py`, replace the `bulk_update_cards` function:

```python
@router.patch("/cards/bulk", response_model=BulkUpdateResult)
def bulk_update_cards(
    payload: list[ZettelCardPatch],
    session: Session = Depends(get_db_session),
) -> BulkUpdateResult:
    svc = ZettelkastenService(session)
    updated: list[int] = []
    missing: list[int] = []

    # Batch-fetch all cards in one query
    requested_ids = [patch.id for patch in payload]
    from sqlmodel import select
    from alfred.models.zettelkasten import ZettelCardRow

    rows = session.exec(
        select(ZettelCardRow).where(ZettelCardRow.id.in_(requested_ids))
    ).all()
    cards_by_id = {card.id: card for card in rows}

    for patch in payload:
        card = cards_by_id.get(patch.id)
        if not card:
            missing.append(patch.id)
            continue
        data = patch.model_dump(exclude_unset=True)
        data.pop("id", None)
        svc.update_card(card, **data)
        updated.append(card.id)

    return BulkUpdateResult(updated_ids=updated, missing_ids=missing)
```

- [ ] **Step 2: Verify the endpoint works**

`cd apps/alfred && python -m pytest tests/ -k "bulk" -v 2>/dev/null || echo "No existing bulk tests found"`

- [ ] **Step 3: Commit**

```
git add apps/alfred/api/zettels/routes.py
git commit -m "perf(zettels): batch-fetch cards in bulk update instead of N+1"
```

---

### Task 4: Add LLM Timeouts and Normalize Cache Keys

**Files:**
- Modify: `apps/alfred/services/llm_service.py:92-98,349-362`
- Modify: `apps/alfred/core/llm_factory.py:13-41`

- [ ] **Step 1: Add timeout to all OpenAI chat completion calls in llm_service.py**

Find every `client.chat.completions.create(` call in `llm_service.py` and add `timeout=30`. There are at least two:

In the main chat call (~line 93):
```python
resp = self.openai_client.chat.completions.create(
    model=model,
    messages=messages,
    temperature=temperature,
    timeout=30,
)
```

In the structured output call (~line 349):
```python
resp = client.chat.completions.create(
    model=model_name,
    messages=messages,
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": schema.__name__,
            "schema": json_schema,
            "strict": True,
        },
    },
    timeout=30,
)
```

Search the file for any other `.create(` calls and add `timeout=30` to those as well.

- [ ] **Step 2: Remove temperature from LLM factory cache key**

In `apps/alfred/core/llm_factory.py`, remove `temperature` from the `get_chat_model` function signature and cache key. Temperature should be passed at the call site instead:

```python
@lru_cache(maxsize=8)
def get_chat_model(
    provider: LLMProvider | None = None,
    model: str | None = None,
) -> BaseChatModel:
    cfg = settings
    provider = provider or cfg.llm_provider
    model = model or cfg.llm_model
    temperature = cfg.llm_temperature

    if provider == LLMProvider.openai:
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=(cfg.openai_api_key.get_secret_value() if cfg.openai_api_key else None),
            base_url=cfg.openai_base_url,
            organization=cfg.openai_organization,
        )

    if provider == LLMProvider.ollama:
        return ChatOllama(
            model=model or cfg.ollama_chat_model,
            temperature=temperature,
            base_url=cfg.ollama_base_url,
        )

    raise ValueError(f"Unsupported provider: {provider}")
```

- [ ] **Step 3: Update all callers of get_chat_model that pass temperature**

Search for `get_chat_model(` across the codebase. Remove `temperature=` arguments from callers since temperature is now always read from settings.

- [ ] **Step 4: Commit**

```
git add apps/alfred/services/llm_service.py apps/alfred/core/llm_factory.py
git commit -m "perf(llm): add 30s timeout to all OpenAI calls, normalize cache keys"
```

---

### Task 5: Create Shared Task Polling Endpoint

**Files:**
- Create: `apps/alfred/api/tasks_status.py`
- Modify: main router file — mount the new router

This task creates the shared infrastructure that Task 6 will use.

- [ ] **Step 1: Find where routers are mounted**

Search for `include_router` in `apps/alfred/api/` to identify the main app file.

- [ ] **Step 2: Create the task status endpoint**

Create `apps/alfred/api/tasks_status.py`:

```python
from __future__ import annotations

import logging

from celery.result import AsyncResult
from fastapi import APIRouter
from pydantic import BaseModel

from alfred.core.celery import create_celery_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

_celery = create_celery_app(include_tasks=False)


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str  # pending | running | completed | failed
    result: object | None = None
    error: str | None = None


_STATE_MAP = {
    "PENDING": "pending",
    "STARTED": "running",
    "RETRY": "running",
    "SUCCESS": "completed",
    "FAILURE": "failed",
    "REVOKED": "failed",
}


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str) -> TaskStatusResponse:
    """Poll the status of an async Celery task."""
    res = AsyncResult(task_id, app=_celery)
    mapped_status = _STATE_MAP.get(res.state, "pending")

    result = None
    error = None
    if mapped_status == "completed":
        result = res.result
    elif mapped_status == "failed":
        error = str(res.result) if res.result else "Task failed"

    return TaskStatusResponse(
        task_id=task_id,
        status=mapped_status,
        result=result,
        error=error,
    )
```

- [ ] **Step 3: Mount the router in the main app**

In the main app file (found in Step 1), add:

```python
from alfred.api.tasks_status import router as tasks_status_router

app.include_router(tasks_status_router)
```

- [ ] **Step 4: Verify the endpoint responds**

Start the API server and test:
`curl -s http://localhost:8000/api/tasks/nonexistent-id | python -m json.tool`

Expected: `{"task_id": "nonexistent-id", "status": "pending", "result": null, "error": null}` (Celery returns PENDING for unknown task IDs).

- [ ] **Step 5: Commit**

```
git add apps/alfred/api/tasks_status.py apps/alfred/api/app.py
git commit -m "feat(api): add shared task polling endpoint GET /api/tasks/{task_id}"
```

---

### Task 6: Move Blocking I/O to Celery

**Files:**
- Modify: `apps/alfred/api/documents/routes.py:178-310`
- Modify: `apps/alfred/api/intelligence/routes.py:39-57`
- Create or modify: `apps/alfred/tasks/document_processing.py`
- Create: `apps/alfred/tasks/planning.py`
- Modify: `apps/alfred/core/celery.py`

- [ ] **Step 1: Convert fetch_and_organize to return a task ID**

In `apps/alfred/api/documents/routes.py`, replace the `fetch_and_organize` function body. Keep validation (doc exists, has source URL, not already fetched) synchronous, but dispatch the actual scraping + enrichment to Celery:

```python
@router.post("/doc/{id}/fetch-and-organize", response_model=FetchOrganizeResponse)
def fetch_and_organize(
    id: str,
    force: bool = Query(False, description="Re-fetch even if content exists"),
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> FetchOrganizeResponse:
    """Kick off async fetch of full page content from source URL via Firecrawl."""
    doc = svc.get_document_details(id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    min_existing_content_length = 500
    existing_text = doc.get("cleaned_text") or ""
    if not force and len(existing_text) > min_existing_content_length:
        return FetchOrganizeResponse(id=id, status="already_has_content", tokens=doc.get("tokens"))

    source_url = doc.get("source_url") or doc.get("canonical_url")
    if not source_url or source_url.startswith("about:"):
        raise HTTPException(status_code=400, detail="No source URL to fetch from")

    celery_client = get_celery_client()
    async_result = celery_client.send_task(
        "alfred.tasks.document_processing.fetch_organize_task",
        kwargs={"doc_id": id, "source_url": source_url, "force": force},
    )
    return FetchOrganizeResponse(
        id=id,
        status="processing",
        task_id=async_result.id,
    )
```

- [ ] **Step 2: Create the Celery task for fetch+organize**

Check if `apps/alfred/tasks/document_processing.py` exists. Add the task there (or create the file):

```python
@celery_app.task(name="alfred.tasks.document_processing.fetch_organize_task", bind=True)
def fetch_organize_task(self, *, doc_id: str, source_url: str, force: bool = False) -> dict:
    """Fetch full page content via Firecrawl, update document, trigger enrichment."""
    from alfred.connectors.firecrawl_connector import FirecrawlClient
    from alfred.services.doc_storage import get_doc_storage_service

    svc = get_doc_storage_service()
    fc = FirecrawlClient()
    result = fc.scrape(source_url)

    if not result.success or not result.markdown:
        return {"status": "error", "error": f"Failed to fetch: {result.error}"}

    markdown = result.markdown.strip()
    if len(markdown) < 50:
        return {"status": "error", "error": "Fetched content too short"}

    svc.update_document_text(doc_id, raw_markdown=markdown, cleaned_text=markdown)

    try:
        from alfred.core.celery import create_celery_app
        client = create_celery_app(include_tasks=False)
        client.send_task(
            "alfred.tasks.document_enrichment.enrich",
            kwargs={"doc_id": doc_id, "force": True},
        )
    except Exception:
        pass

    return {"status": "fetched_and_enriching", "tokens": len(markdown.split())}
```

- [ ] **Step 3: Convert generate_document_image to async**

In `apps/alfred/api/documents/routes.py`, update `generate_document_image` to dispatch to the existing Celery task instead of calling synchronously:

```python
@router.post("/{id}/image", response_model=DocumentTitleImageResponse)
def generate_document_image(
    id: str,
    force: bool = Query(False, description="Regenerate even if already present"),
    payload: DocumentTitleImageRequest = Body(default_factory=DocumentTitleImageRequest),
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> DocumentTitleImageResponse:
    """Queue cover image generation as a background task."""
    doc = svc.get_document_details(id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    celery_client = get_celery_client()
    async_result = celery_client.send_task(
        "alfred.tasks.document_title_image.document_title_image_task",
        kwargs={
            "doc_id": id,
            "force": force,
            "model": payload.model,
            "size": payload.size,
            "quality": payload.quality,
        },
    )
    return DocumentTitleImageResponse(
        id=id,
        status="processing",
        cover_image_url=f"/api/documents/{id}/image",
        task_id=async_result.id,
    )
```

Note: Check if `DocumentTitleImageResponse` and `FetchOrganizeResponse` have a `task_id` field. If not, add `task_id: str | None = None` to each.

- [ ] **Step 4: Convert planning endpoint to async**

In `apps/alfred/api/intelligence/routes.py`:

```python
@router.post(
    "/plan",
    status_code=status.HTTP_202_ACCEPTED,
)
def create_plan(payload: PlanCreateRequest) -> dict:
    """Queue plan generation as a background task."""
    from alfred.core.celery import create_celery_app

    celery_client = create_celery_app(include_tasks=False)
    async_result = celery_client.send_task(
        "alfred.tasks.planning.generate_plan_task",
        kwargs={
            "goal": payload.goal,
            "context": payload.context,
            "max_steps": payload.max_steps,
        },
    )
    return {"task_id": async_result.id, "status": "pending"}
```

- [ ] **Step 5: Create the planning Celery task**

Create `apps/alfred/tasks/planning.py`:

```python
from __future__ import annotations

import logging

from alfred.core.celery import create_celery_app

logger = logging.getLogger(__name__)
celery_app = create_celery_app(include_tasks=False)


@celery_app.task(name="alfred.tasks.planning.generate_plan_task")
def generate_plan_task(*, goal: str, context: str | None = None, max_steps: int = 6) -> dict:
    from alfred.services.planning_service import PlanningService

    svc = PlanningService()
    plan = svc.create_plan(goal=goal, context=context, max_steps=max_steps)
    return plan.model_dump()
```

- [ ] **Step 6: Register new tasks in Celery config**

In `apps/alfred/core/celery.py`, add `"alfred.tasks.planning"` to `task_modules` list. Add route `"alfred.tasks.planning.*": {"queue": "default"}`. Add explicit import `import alfred.tasks.planning` at the bottom.

- [ ] **Step 7: Commit**

```
git add apps/alfred/api/documents/routes.py apps/alfred/api/intelligence/routes.py apps/alfred/tasks/ apps/alfred/core/celery.py
git commit -m "perf(api): move blocking scraping, image gen, and planning to Celery tasks"
```

---

### Task 7: Use celery.group() for Batch Dispatch

**Files:**
- Modify: `apps/alfred/tasks/document_title_image.py:61-84`

- [ ] **Step 1: Replace the delay loop with celery.group**

In `apps/alfred/tasks/document_title_image.py`, replace the `enqueue_only` branch:

```python
if enqueue_only:
    from celery import group

    job = group(
        document_title_image_task.s(
            doc_id=did,
            force=bool(force),
            model=str(model),
            size=str(size),
            quality=str(quality),
        )
        for did in doc_ids
    )
    group_result = job.apply_async()
    task_ids = [r.id for r in group_result.results]
    return {"ok": True, "queued": len(task_ids), "doc_ids": doc_ids, "task_ids": task_ids}
```

- [ ] **Step 2: Commit**

```
git add apps/alfred/tasks/document_title_image.py
git commit -m "perf(celery): use group() for parallel batch image generation dispatch"
```

---

### Task 8: Normalize Agent Store Messages to Indexed Map

**Files:**
- Modify: `web/lib/stores/agent-store.ts`

This is the most impactful frontend change. Currently the store maps over the entire messages array on every 50ms token flush.

- [ ] **Step 1: Update the state type**

In `web/lib/stores/agent-store.ts`, replace the `messages` field in `AgentState`:

```typescript
// OLD:
//   messages: AgentMessage[];

// NEW:
messagesById: Record<number, AgentMessage>;
messageOrder: number[];
```

Add a selector function outside the store:

```typescript
/** Derive ordered messages array from indexed store. Memoize in components via useMemo. */
export function selectOrderedMessages(state: {
  messagesById: Record<number, AgentMessage>;
  messageOrder: number[];
}): AgentMessage[] {
  return state.messageOrder.map((id) => state.messagesById[id]);
}
```

- [ ] **Step 2: Update the token buffer flush**

Replace `_flushTokenBuffer` to only mutate the single streaming message:

```typescript
function _flushTokenBuffer(
  set: (fn: (s: AgentState) => Partial<AgentState>) => void,
) {
  if (!_tokenBuffer) return;
  const buffered = _tokenBuffer;
  _tokenBuffer = "";
  _tokenFlushTimer = null;
  set((s) => {
    const lastId = s.messageOrder[s.messageOrder.length - 1];
    const lastMsg = s.messagesById[lastId];
    if (!lastMsg || lastMsg.role !== "assistant") return {};
    return {
      messagesById: {
        ...s.messagesById,
        [lastId]: { ...lastMsg, content: lastMsg.content + buffered },
      },
    };
  });
}
```

- [ ] **Step 3: Update sendMessage to use indexed storage**

In the `sendMessage` action, replace message array operations:

```typescript
const userMsg: AgentMessage = {
  id: Date.now(),
  role: "user",
  content: text,
  /* ... other fields */
};
const assistantMsg: AgentMessage = {
  id: Date.now() + 1,
  role: "assistant",
  content: "",
  /* ... other fields */
};

set((s) => ({
  messagesById: {
    ...s.messagesById,
    [userMsg.id]: userMsg,
    [assistantMsg.id]: assistantMsg,
  },
  messageOrder: [...s.messageOrder, userMsg.id, assistantMsg.id],
  isStreaming: true,
}));
```

- [ ] **Step 4: Update _handleSSEEvent to use indexed storage**

For each event type that modifies the last message (`artifact`, `related`, `gaps`, `tool_result`, `error`), use this pattern:

```typescript
set((s) => {
  const lastId = s.messageOrder[s.messageOrder.length - 1];
  const lastMsg = s.messagesById[lastId];
  if (!lastMsg || lastMsg.role !== "assistant") return {};
  return {
    messagesById: {
      ...s.messagesById,
      [lastId]: {
        ...lastMsg,
        artifacts: [...(lastMsg.artifacts || []), newArtifact],
      },
    },
  };
});
```

Apply this pattern to all event handlers: `"artifact"`, `"related"`, `"gaps"`, `"tool_result"`, `"error"`.

- [ ] **Step 5: Update loadThread to use indexed storage**

In `loadThread`, when setting messages from API response:

```typescript
const byId: Record<number, AgentMessage> = {};
const order: number[] = [];
for (const msg of apiMessages) {
  byId[msg.id] = msg;
  order.push(msg.id);
}
set({ messagesById: byId, messageOrder: order, activeThreadId: threadId });
```

- [ ] **Step 6: Update clearMessages**

```typescript
clearMessages: () => set({ messagesById: {}, messageOrder: [] }),
```

- [ ] **Step 7: Increase token flush interval from 50ms to 120ms**

Find the `setTimeout` call in `_handleSSEEvent` for the `"token"` event:

```typescript
// OLD:
_tokenFlushTimer = setTimeout(() => _flushTokenBuffer(set), 50);
// NEW:
_tokenFlushTimer = setTimeout(() => _flushTokenBuffer(set), 120);
```

- [ ] **Step 8: Move activeToolCalls to a separate slice**

Add a separate mini-store for tool calls at the bottom of `agent-store.ts`:

```typescript
interface ToolCallState {
  activeToolCalls: ToolCall[];
  addToolCall: (tc: ToolCall) => void;
  updateLastToolCall: (update: Partial<ToolCall>) => void;
  clearToolCalls: () => void;
}

export const useToolCallStore = create<ToolCallState>((set) => ({
  activeToolCalls: [],
  addToolCall: (tc) =>
    set((s) => ({ activeToolCalls: [...s.activeToolCalls, tc] })),
  updateLastToolCall: (update) =>
    set((s) => {
      const calls = [...s.activeToolCalls];
      if (calls.length > 0)
        calls[calls.length - 1] = { ...calls[calls.length - 1], ...update };
      return { activeToolCalls: calls };
    }),
  clearToolCalls: () => set({ activeToolCalls: [] }),
}));
```

Remove `activeToolCalls` from the main `AgentState`. Update `_handleSSEEvent` to use `useToolCallStore.getState()` for `tool_start` and `tool_result` events.

- [ ] **Step 9: Commit**

```
git add web/lib/stores/agent-store.ts
git commit -m "perf(store): normalize messages to indexed map, separate tool call store, increase flush to 120ms"
```

---

### Task 9: Add Zustand Selectors to All Store Consumers

**Files:**
- Modify: `web/app/(app)/agent/_components/agent-chat-client.tsx`
- Modify: `web/app/(app)/_components/ai-panel.tsx`

- [ ] **Step 1: Update agent-chat-client.tsx to use selectors**

Replace the full state destructure with targeted selectors:

```typescript
import { useShallow } from "zustand/react/shallow";
import {
  useAgentStore,
  useToolCallStore,
  selectOrderedMessages,
} from "@/lib/stores/agent-store";

const {
  messagesById,
  messageOrder,
  threads,
  activeThreadId,
  isStreaming,
  activeLens,
  activeModel,
  sendMessage,
  cancelStream,
  setLens,
  setModel,
  loadThreads,
  createThread,
  clearMessages,
} = useAgentStore(
  useShallow((s) => ({
    messagesById: s.messagesById,
    messageOrder: s.messageOrder,
    threads: s.threads,
    activeThreadId: s.activeThreadId,
    isStreaming: s.isStreaming,
    activeLens: s.activeLens,
    activeModel: s.activeModel,
    sendMessage: s.sendMessage,
    cancelStream: s.cancelStream,
    setLens: s.setLens,
    setModel: s.setModel,
    loadThreads: s.loadThreads,
    createThread: s.createThread,
    clearMessages: s.clearMessages,
  })),
);

const messages = useMemo(
  () => selectOrderedMessages({ messagesById, messageOrder }),
  [messagesById, messageOrder],
);
const { activeToolCalls } = useToolCallStore(
  useShallow((s) => ({ activeToolCalls: s.activeToolCalls })),
);
```

- [ ] **Step 2: Update ai-panel.tsx to use selectors**

Apply the same pattern, also adding `noteContext` to the selector:

```typescript
import { useShallow } from "zustand/react/shallow";
import {
  useAgentStore,
  useToolCallStore,
  selectOrderedMessages,
} from "@/lib/stores/agent-store";

const {
  messagesById,
  messageOrder,
  threads,
  activeThreadId,
  isStreaming,
  activeLens,
  activeModel,
  noteContext,
  sendMessage,
  cancelStream,
  setLens,
  setModel,
  loadThreads,
  createThread,
  clearMessages,
} = useAgentStore(
  useShallow((s) => ({
    messagesById: s.messagesById,
    messageOrder: s.messageOrder,
    threads: s.threads,
    activeThreadId: s.activeThreadId,
    isStreaming: s.isStreaming,
    activeLens: s.activeLens,
    activeModel: s.activeModel,
    noteContext: s.noteContext,
    sendMessage: s.sendMessage,
    cancelStream: s.cancelStream,
    setLens: s.setLens,
    setModel: s.setModel,
    loadThreads: s.loadThreads,
    createThread: s.createThread,
    clearMessages: s.clearMessages,
  })),
);

const messages = useMemo(
  () => selectOrderedMessages({ messagesById, messageOrder }),
  [messagesById, messageOrder],
);
const { activeToolCalls } = useToolCallStore(
  useShallow((s) => ({ activeToolCalls: s.activeToolCalls })),
);
```

- [ ] **Step 3: Fix the AI panel thread caching issue**

In `ai-panel.tsx`, replace the `loadThreads` effect with a stale-check:

```typescript
const lastThreadLoadRef = useRef(0);

useEffect(() => {
  if (!aiPanelOpen) return;
  const now = Date.now();
  if (now - lastThreadLoadRef.current > 60_000) {
    loadThreads();
    lastThreadLoadRef.current = now;
  }
  setTimeout(() => inputRef.current?.focus(), 200);
}, [aiPanelOpen, loadThreads]);
```

- [ ] **Step 4: Commit**

```
git add web/app/(app)/agent/_components/agent-chat-client.tsx web/app/(app)/_components/ai-panel.tsx
git commit -m "perf(frontend): add Zustand useShallow selectors, fix AI panel thread re-fetching"
```

---

### Task 10: Memoize List Components and Callbacks

**Files:**
- Modify: `web/app/(app)/agent/_components/agent-chat-client.tsx`
- Modify: `web/app/(app)/_components/ai-panel.tsx`
- Modify: `web/app/(app)/research/_components/research-client.tsx`

- [ ] **Step 1: Memoize MessageBubble in agent-chat-client.tsx**

Add `memo` to imports and wrap the component:

```typescript
import { memo, useCallback, useMemo } from "react";

const handleArtifactClick = useCallback((card: ArtifactCard) => {
  setEditingZettelId(card.id);
}, []);

const MessageBubble = memo(function MessageBubble({
  message,
  onArtifactClick,
}: {
  message: AgentMessage;
  onArtifactClick: (card: ArtifactCard) => void;
}) {
  // ... existing body unchanged
});
```

- [ ] **Step 2: Memoize PanelMessage in ai-panel.tsx**

```typescript
const handleArtifactClick = useCallback((card: ArtifactCard) => {
  setEditingZettelId(card.id);
}, []);

const PanelMessage = memo(function PanelMessage({
  message,
  onArtifactClick,
}: {
  message: AgentMessage;
  onArtifactClick: (card: ArtifactCard) => void;
}) {
  // ... existing body unchanged
});
```

- [ ] **Step 3: Memoize ReportListItem in research-client.tsx**

Update `ReportListItem` to accept `onSelect` + `reportId` instead of a pre-bound `onClick`:

```typescript
import { memo, useCallback } from "react";

const ReportListItem = memo(function ReportListItem({
  report,
  isActive,
  onSelect,
}: {
  report: ResearchReportSummary;
  isActive: boolean;
  onSelect: (id: string) => void;
}) {
  const handleClick = useCallback(
    () => onSelect(report.id),
    [onSelect, report.id],
  );
  // ... existing body, use handleClick for the button onClick
});
```

In the parent `ReportThreadList`, stabilize the callback:

```typescript
const handleReportSelect = useCallback(
  (reportId: string) => {
    onSelect(reportId);
  },
  [onSelect],
);

// In JSX:
{filtered.map((report) => (
  <ReportListItem
    key={report.id}
    report={report}
    isActive={selectedId === report.id}
    onSelect={handleReportSelect}
  />
))}
```

- [ ] **Step 4: Commit**

```
git add web/app/(app)/agent/_components/agent-chat-client.tsx web/app/(app)/_components/ai-panel.tsx web/app/(app)/research/_components/research-client.tsx
git commit -m "perf(components): memoize MessageBubble, PanelMessage, ReportListItem with stable callbacks"
```

---

### Task 11: Dynamic Import Three.js and TipTap

**Files:**
- Find and modify: components that import from `three`, `@react-three/fiber`, `@react-three/drei`
- Find and modify: page-level imports of the TipTap editor component

- [ ] **Step 1: Find Three.js imports**

Search for Three.js imports across the frontend:
- Look for `from "three"`, `from "@react-three/fiber"`, `from "@react-three/drei"` in `.tsx` and `.ts` files under `web/`

Identify which components import Three.js and which pages render them.

- [ ] **Step 2: Wrap Three.js components with next/dynamic**

For each page that renders a Three.js component, create a dynamic wrapper following the existing Excalidraw pattern in `web/app/(app)/canvas/_components/excalidraw-whiteboard.tsx`:

```typescript
import dynamic from "next/dynamic";

const SemanticMapVisualization = dynamic(
  () => import("@/components/documents/semantic-map-visualization"),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Loading visualization...
      </div>
    ),
  },
);
```

Replace direct imports of the Three.js component in each page with the dynamic version.

- [ ] **Step 3: Find TipTap imports**

Search for `from "@tiptap` imports to identify where TipTap is loaded.

- [ ] **Step 4: Wrap TipTap editor with next/dynamic**

The main editor component is `web/components/editor/markdown-notes-editor.tsx` (862 lines). At the page level where it's imported, use dynamic import:

```typescript
import dynamic from "next/dynamic";

const MarkdownNotesEditor = dynamic(
  () => import("@/components/editor/markdown-notes-editor"),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Loading editor...
      </div>
    ),
  },
);
```

- [ ] **Step 5: Commit**

```
git add web/
git commit -m "perf(bundle): dynamic import Three.js and TipTap editor to reduce initial bundle"
```

---

### Task 12: Add Route Loading Skeletons

**Files:**
- Create: `web/app/(app)/dashboard/loading.tsx`
- Create: `web/app/(app)/documents/loading.tsx`
- Create: `web/app/(app)/research/loading.tsx`
- Create: `web/app/(app)/agent/loading.tsx`
- Create: `web/app/(app)/notes/loading.tsx`

- [ ] **Step 1: Check existing loading.tsx files and Skeleton component**

Verify no loading.tsx files already exist. Confirm that `@/components/ui/skeleton` exports a `Skeleton` component (shadcn/ui standard).

- [ ] **Step 2: Create dashboard loading skeleton**

Create `web/app/(app)/dashboard/loading.tsx`:

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardLoading() {
  return (
    <div className="mx-auto max-w-5xl space-y-8 p-6">
      <Skeleton className="h-32 w-full rounded-lg" />
      <div className="grid grid-cols-3 gap-4">
        <Skeleton className="h-48 rounded-lg" />
        <Skeleton className="h-48 rounded-lg" />
        <Skeleton className="h-48 rounded-lg" />
      </div>
      <Skeleton className="h-64 w-full rounded-lg" />
      <Skeleton className="h-24 w-full rounded-lg" />
    </div>
  );
}
```

- [ ] **Step 3: Create documents loading skeleton**

Create `web/app/(app)/documents/loading.tsx`:

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function DocumentsLoading() {
  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <Skeleton className="h-10 w-64" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-48 rounded-lg" />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create research loading skeleton**

Create `web/app/(app)/research/loading.tsx`:

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function ResearchLoading() {
  return (
    <div className="flex h-full">
      <div className="w-[280px] space-y-3 border-r p-4">
        <Skeleton className="h-8 w-full" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full rounded-lg" />
        ))}
      </div>
      <div className="flex-1 space-y-4 p-6">
        <Skeleton className="h-8 w-96" />
        <Skeleton className="h-32 w-full rounded-lg" />
        <div className="grid grid-cols-3 gap-4">
          <Skeleton className="h-24 rounded-lg" />
          <Skeleton className="h-24 rounded-lg" />
          <Skeleton className="h-24 rounded-lg" />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create agent loading skeleton**

Create `web/app/(app)/agent/loading.tsx`:

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function AgentLoading() {
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col p-6">
      <Skeleton className="mb-6 h-8 w-48" />
      <div className="flex-1 space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full rounded-lg" />
        ))}
      </div>
      <Skeleton className="mt-4 h-24 w-full rounded-lg" />
    </div>
  );
}
```

- [ ] **Step 6: Create notes loading skeleton**

Create `web/app/(app)/notes/loading.tsx`:

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function NotesLoading() {
  return (
    <div className="flex h-full">
      <div className="w-64 space-y-2 border-r p-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full rounded" />
        ))}
      </div>
      <div className="flex-1 p-8">
        <Skeleton className="mb-4 h-10 w-96" />
        <Skeleton className="h-[60vh] w-full rounded-lg" />
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Commit**

```
git add web/app/(app)/dashboard/loading.tsx web/app/(app)/documents/loading.tsx web/app/(app)/research/loading.tsx web/app/(app)/agent/loading.tsx web/app/(app)/notes/loading.tsx
git commit -m "perf(ux): add loading skeletons for all major routes"
```

---

## Phase 2: Hot Path Optimization

### Task 13: Create useTaskPolling Frontend Hook

**Files:**
- Create: `web/hooks/use-task-polling.ts`

- [ ] **Step 1: Check existing hooks directory and apiFetch import path**

Verify `web/hooks/` exists. Check how `apiFetch` is imported in other hooks/features (e.g., look at `web/features/documents/queries.ts` for the import pattern).

- [ ] **Step 2: Create the shared polling hook**

Create `web/hooks/use-task-polling.ts`:

```typescript
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/fetch";

interface TaskStatus {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed";
  result: unknown;
  error: string | null;
}

/**
 * Poll a Celery task status until it reaches a terminal state.
 * Polls every 2s while pending/running, stops on completed/failed.
 */
export function useTaskPolling(taskId: string | null) {
  return useQuery<TaskStatus>({
    queryKey: ["task-status", taskId],
    queryFn: () => apiFetch<TaskStatus>(`/api/tasks/${taskId}`),
    enabled: Boolean(taskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed") return false;
      return 2000;
    },
    staleTime: 0,
  });
}
```

Note: Verify the `apiFetch` signature matches. It might be `apiFetch(url)` or `apiFetch<T>(url, options)`. Check the existing import in `web/features/documents/queries.ts`.

- [ ] **Step 3: Commit**

```
git add web/hooks/use-task-polling.ts
git commit -m "feat(hooks): add useTaskPolling for async Celery task status polling"
```

---

### Task 14: Semantic Map Cache Optimization

**Files:**
- Modify: `apps/alfred/services/doc_storage/_semantic_map_mixin.py:115-124`
- Modify: `apps/alfred/api/documents/routes.py` (semantic map endpoint)

- [ ] **Step 1: Replace DB version check with Redis version key**

In `apps/alfred/services/doc_storage/_semantic_map_mixin.py`, update `_current_semantic_map_version`:

```python
def _current_semantic_map_version(self) -> str:
    """Return a version string for cache invalidation.

    Checks Redis first for a cached version key (set on document changes).
    Falls back to DB query only if Redis is unavailable or key is missing.
    """
    if self.redis_client is not None:
        try:
            cached = self.redis_client.get("semantic_map:version")
            if cached:
                return cached
        except Exception:
            pass

    with _session_scope(self.session) as s:
        ts = s.scalar(select(func.max(DocumentRow.updated_at)))
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        version = ts.isoformat()
    else:
        version = "none"

    if self.redis_client is not None:
        try:
            self.redis_client.setex("semantic_map:version", 60, version)
        except Exception:
            pass

    return version
```

- [ ] **Step 2: Add version bump method and call it on document changes**

Add to the mixin class:

```python
def _bump_semantic_map_version(self) -> None:
    """Invalidate cached semantic map version so next request recomputes."""
    if self.redis_client is not None:
        try:
            self.redis_client.delete("semantic_map:version")
        except Exception:
            pass
```

Find `update_document_text()`, `create_document()`, and `delete_document()` methods in the doc_storage service. Add `self._bump_semantic_map_version()` call after each.

- [ ] **Step 3: Reduce default semantic map limit**

In `apps/alfred/api/documents/routes.py`, change the default:

```python
@router.get("/semantic-map", response_model=SemanticMapResponse)
def get_semantic_map(
    limit: int = Query(2000, ge=1, le=20_000),  # Reduced from 5000
    refresh: bool = Query(False, description="Force recompute (bypass cache)"),
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> dict:
```

- [ ] **Step 4: Commit**

```
git add apps/alfred/services/doc_storage/_semantic_map_mixin.py apps/alfred/api/documents/routes.py
git commit -m "perf(semantic-map): Redis version-key cache, reduce default limit to 2000"
```

---

### Task 15: Fix Document staleTime

**Files:**
- Modify: `web/features/documents/queries.ts`

- [ ] **Step 1: Update staleTime for document details**

In `web/features/documents/queries.ts`, find `useDocumentDetails` and change `staleTime` from `0` to `30_000`:

```typescript
export function useDocumentDetails(docId: string | null) {
  return useQuery({
    enabled: Boolean(docId),
    queryKey: docId
      ? documentDetailsQueryKey(docId)
      : ["documents", "details", "disabled"],
    queryFn: () => getDocumentDetails(docId!),
    staleTime: 30_000, // Was 0
  });
}
```

- [ ] **Step 2: Commit**

```
git add web/features/documents/queries.ts
git commit -m "perf(queries): set document details staleTime to 30s instead of always-stale"
```

---

## Phase 3: Polish

### Task 16: CSS Paint Performance Optimization

**Files:**
- Modify: `web/app/globals.css`

- [ ] **Step 1: GPU-promote the grain overlay**

In `web/app/globals.css`, find the `body::before` rule (~line 321). Add `will-change: transform`:

```css
body::before {
  content: '';
  position: fixed;
  inset: 0;
  opacity: var(--alfred-grain-opacity);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='256' height='256'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.5'/%3E%3C/svg%3E");
  background-repeat: repeat;
  background-size: 256px 256px;
  pointer-events: none;
  z-index: 9999;
  will-change: transform;
}
```

- [ ] **Step 2: Add prefers-reduced-motion for animations**

After the animation definitions (~line 522), add:

```css
@media (prefers-reduced-motion: reduce) {
  .animate-arcane-float,
  .animate-arcane-spin,
  .animate-atheneum-warp {
    animation: none !important;
  }
}
```

- [ ] **Step 3: Commit**

```
git add web/app/globals.css
git commit -m "perf(css): GPU-promote grain overlay, respect prefers-reduced-motion"
```

---

### Task 17: Standardize React Query Cache Strategy

**Files:**
- Modify: Various query files across `web/features/`

- [ ] **Step 1: Audit all query staleTime values**

Search for `staleTime` across all `.ts` and `.tsx` files in `web/` (excluding node_modules and .next). List each file and current value.

- [ ] **Step 2: Apply standardized values**

Apply the cache strategy from the spec:

| Category | staleTime | Examples |
|----------|-----------|-------|
| Real-time (SSE) | `0` | Agent streaming queries only |
| User content | `30_000` | Documents, zettels, research reports |
| Computed/expensive | `300_000` | Semantic map |
| Static-ish | `600_000` | Connector status, settings |

Update each query hook file to match. The semantic map currently has `10 * 60 * 1000` — standardize to `300_000`.

- [ ] **Step 3: Commit**

```
git add web/features/
git commit -m "perf(cache): standardize React Query staleTime across all query hooks"
```

---

### Task 18: Add FastAPI Response Compression

**Files:**
- Modify: main FastAPI app file

- [ ] **Step 1: Check if compression middleware already exists**

Search for `GZip`, `gzip`, `Compression`, or `brotli` in `apps/alfred/`.

- [ ] **Step 2: Add GZip middleware if not present**

In the main FastAPI app file, add after app creation:

```python
from starlette.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

This compresses all responses over 1KB with gzip automatically.

- [ ] **Step 3: Commit**

```
git add apps/alfred/api/
git commit -m "perf(api): add GZip middleware for response compression"
```

---

## Final Verification

### Task 19: Verify All Changes

- [ ] **Step 1: Run backend tests**

`cd apps/alfred && python -m pytest tests/ -v --timeout=60`

Expected: All tests pass.

- [ ] **Step 2: Run frontend build**

`cd web && npm run build`

Expected: Build succeeds. Note the bundle size output for comparison with pre-optimization baseline.

- [ ] **Step 3: Run frontend type check**

`cd web && npx tsc --noEmit`

Expected: No type errors.

- [ ] **Step 4: Smoke test the app**

Start both backend and frontend. Navigate through:
1. Dashboard — should show skeleton then load
2. Documents — should load, semantic map should work
3. Agent chat — send a message, verify streaming works without jank
4. Research — click through reports, verify list is responsive
5. Notes — verify editor loads (dynamically imported)

- [ ] **Step 5: Fix any issues found and commit**

```
git add -A
git commit -m "fix: address issues found during performance verification"
```
