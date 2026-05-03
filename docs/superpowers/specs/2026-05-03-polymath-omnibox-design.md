# Polymath Omnibox + Visible Rebrand Design

**Date:** 2026-05-03  
**Status:** Approved design; awaiting implementation plan  
**Scope:** Upgrade the chatbox `@` function into a keyword-first mixed search surface and rename visible product UI text from Alfred to Polymath.  

## Goal

Make the chatbox `@` function feel like Polymath's command center: a fast keyword search surface that can attach knowledge context and trigger obvious chat actions without requiring an AI call on every keystroke.

This first pass should make `@` materially more useful while staying small enough to ship safely:

- Search zettels by title, topic, tags, summary, and content.
- Search documents by title and cleaned text.
- Show action rows for common intents like searching all knowledge or creating a card from the current phrase.
- Attach selected zettels and documents as removable context chips.
- Send attached context as hidden structured prompt context while keeping the visible user message clean.
- Rename visible user-facing product text from Alfred to Polymath.

## Current State

The chat component already has a zettel-only `@` picker in `web/components/chat/unified-chat.tsx`.

Current behavior:

- Typing `@memo` detects the latest mention token.
- The frontend calls `searchCards(query)` through React Query.
- The backend route `GET /api/zettels/cards/search` returns recent cards for bare `@` and title-only `ILIKE` matches for keyword queries.
- Selecting a card fetches the full card, renders an `@Title` chip, removes the mention token from the visible textarea, and sends a hidden `Referenced zettels:` context block.

Observed gap:

- Keyword search does not feel powerful because zettel search only matches titles. Tags, topics, summaries, and card content are invisible to `@`.
- The picker is named and shaped around zettels only, so it cannot grow cleanly into documents and actions.
- A cache-key collision could prevent selected zettels from loading raw card details if the transformed detail-view cache was already populated. This has been fixed by using a chat-specific raw zettel query key.

## Product Decision

Use **Option B: Polymath Omnibox**.

The Omnibox is not a deep research engine yet. It is a fast mixed result picker that upgrades `@` from a zettel attach affordance into a compact knowledge and action surface.

## User Experience

### Trigger

The Omnibox opens when the current textarea token matches:

- `@`
- `@keyword`
- `@multi-word query` until the cursor exits the mention span or the user selects a result.

If the user types a bare `@`, the Omnibox shows recent useful results and a small set of default actions. If the user types a query, it ranks matching zettels, documents, and actions.

### Result Groups

Results are grouped in one list:

1. **Zettels**  
   Small card rows with title, topic, up to three tags, and a short matched excerpt when available.

2. **Documents**  
   Rows with title, primary topic or source domain, and a short summary or matched excerpt.

3. **Actions**  
   Deterministic rows derived from the query, such as:
   - Search all knowledge for `<query>`
   - Create card from `<query>`

### Selection Behavior

Selecting a zettel or document:

- Fetches the raw detail needed for prompt context.
- Adds a removable chip above the composer.
- Removes the active `@...` token from the visible textarea.
- Returns focus to the textarea.

Selecting an action:

- Keeps the user's visible message clean.
- Inserts or attaches an internal instruction depending on the action type.
- For v1, actions should be simple and deterministic. They should not start a background workflow until the user sends the message.

### Keyboard Behavior

- `ArrowDown` / `ArrowUp`: move through result rows.
- `Enter`: select highlighted Omnibox row when open; otherwise send the chat message.
- `Escape`: close the Omnibox.
- `Backspace` on an empty mention token closes the Omnibox.

Mouse selection should use `onMouseDown` prevention so the textarea does not blur before the result is processed.

## Architecture

### Frontend Modules

Keep most work near the existing chat feature, but rename internal UI concepts from "mention picker" to "omnibox" where the code is touched.

Proposed frontend shapes:

```ts
type OmniboxResult =
  | {
      kind: "zettel";
      id: number;
      title: string;
      topic: string | null;
      tags: string[];
      excerpt?: string | null;
      score?: number;
    }
  | {
      kind: "document";
      id: string;
      title: string;
      topic: string | null;
      sourceUrl?: string | null;
      excerpt?: string | null;
      score?: number;
    }
  | {
      kind: "action";
      id: string;
      title: string;
      description: string;
      action: "search_all" | "create_card";
      query: string;
    };
```

Attached context should become mixed instead of zettel-only:

```ts
type AttachedChatContext =
  | {
      kind: "zettel";
      id: number;
      title: string;
      content: string | null;
      summary: string | null;
      topic: string | null;
      tags: string[] | null;
    }
  | {
      kind: "document";
      id: string;
      title: string;
      cleanedText: string;
      summary: unknown;
      sourceUrl: string | null;
      topics: unknown;
    };
```

### API Shape

Add a dedicated mixed search endpoint rather than stretching the existing zettel search contract:

```http
GET /api/chat/omnibox?q=<query>&limit=8
```

Response:

```json
{
  "results": [
    {
      "kind": "zettel",
      "id": 158,
      "title": "Gist Memory",
      "topic": "Cognitive Psychology",
      "tags": ["memory", "gist"],
      "excerpt": "Gist memory refers to remembering the general meaning...",
      "score": 21.4
    }
  ]
}
```

The implementation should add this endpoint as a new backend chat API route. The frontend should consume this one mixed Omnibox endpoint rather than manually merging unrelated endpoints inside the chat component.

### Backend Search

The first pass should stay SQL-backed and deterministic.

Zettel search should match:

- `title`
- `topic`
- `summary`
- `content`
- `tags`

Document search should match:

- `title`
- `cleaned_text`
- `summary` when stored as searchable text or JSON text
- primary topic and classification fields when present

Ranking should be simple and transparent:

- Exact title match ranks highest.
- Prefix title match ranks next.
- Title substring ranks above topic/tag.
- Topic/tag matches rank above summary/content.
- More recently updated/captured items break ties.

No LLM call should run during keystroke search. The action rows can instruct the later chat turn to use broader retrieval once the user sends.

## Prompt Context

The hidden context block should become source-typed:

```text
Referenced Polymath context:

Zettel [158] Gist Memory
Topic: Cognitive Psychology | Tags: memory, gist
Excerpt: Gist memory is the remembered essence...

Document [<uuid>] Title
Source: https://...
Excerpt: ...

Use the referenced context explicitly. It is selected by the user, but it is not necessarily exhaustive.
```

The visible `displayText` remains the user-authored message after removing selected `@...` tokens.

## Polymath Rebrand Scope

This pass renames only visible product UI text.

In scope:

- Chat headers: `Alfred AI` -> `Polymath AI`.
- Empty state copy and descriptions that mention Alfred.
- Landing page and app shell product copy visible to users.
- Chrome extension visible labels and page titles where they say Alfred.
- User-facing prompts or descriptions where the product speaks as Alfred.

Out of scope:

- Python package name `alfred`.
- API routes.
- Environment variables.
- Database tables and migrations.
- CSS variables like `--alfred-accent-subtle`.
- Local storage keys.
- Import paths.
- Docker service names.
- Test fixture identifiers that are not user-visible.

This split keeps the rebrand safe while preserving compatibility with existing backend code, extension storage, deployment config, and developer workflows.

## Error Handling

- If mixed Omnibox search fails, show a compact row saying search is unavailable and let normal chat continue.
- If detail fetch for a selected zettel/document fails, keep the textarea text unchanged and do not add a chip.
- If there are no keyword results, show the action rows so the user can still ask Polymath to search all knowledge.
- If the user sends with attached context and the model call fails, keep existing chat error behavior.

## Accessibility

- The Omnibox should be announced as a listbox.
- Rows should expose role `option` and selected state.
- Chips should expose clear remove labels, e.g. `Remove Gist Memory context`.
- Keyboard selection must work without mouse input.

## Tests

Frontend tests:

- Typing `@memory` shows mixed Omnibox rows.
- Selecting a zettel attaches a chip and sends source-typed hidden context.
- Selecting a document attaches a chip and sends source-typed hidden context.
- `Enter` selects an open Omnibox row before sending chat.
- `Escape` closes the Omnibox.
- Visible product text says Polymath in chat header and empty state.

Backend tests:

- Zettel Omnibox search matches title.
- Zettel Omnibox search matches topic/tag.
- Zettel Omnibox search matches summary/content.
- Document Omnibox search returns matching document rows.
- Bare query returns recent zettels/documents and action rows.
- Ranking prefers title matches over body matches.

Rebrand tests:

- Update affected UI text assertions from Alfred to Polymath.
- Keep internal route/storage/env names unchanged.

## Rollout

1. Fix the existing `@` zettel attachment path and keep current tests passing.
2. Add backend mixed Omnibox search contract.
3. Replace zettel-only picker with grouped Omnibox UI.
4. Expand context chips and hidden prompt formatting for mixed sources.
5. Rename visible product text to Polymath.
6. Run focused frontend and backend tests.

## Non-Goals

- No global package rename from `alfred` to `polymath`.
- No migration of storage keys.
- No vector search requirement for v1.
- No AI reranking on keystroke.
- No deep evidence pack generation in the picker.
- No redesign of the entire app shell beyond visible text replacement.
