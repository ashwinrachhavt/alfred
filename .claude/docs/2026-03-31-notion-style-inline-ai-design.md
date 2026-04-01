# Notion-Style Inline AI for Notes Editor

**Date:** 2026-03-31
**Branch:** touch-up-3
**Status:** Approved — ready for implementation planning

## Problem

The notes editor's AI features require preconditions to use:
- Selection bubble menu: requires selecting text
- Cmd+J prompt: requires existing text in the paragraph
- Slash commands: requires typing `/`

None offer a persistent, always-available AI writing assistant. The user wants Notion AI-style fluidity where AI is always one gesture away, adapting to context.

## Design Decisions

### 1. Trigger Model

Three triggers, all opening the same `<InlineAIPrompt>` component:

| Trigger | Context | Behavior |
|---------|---------|----------|
| **Space on empty paragraph** | Cursor on completely empty line | Opens AI prompt inline at cursor. Placeholder: "Ask AI to write..." |
| **Cmd+J** | Anywhere (empty line, text, selection) | Opens AI prompt. Adapts mode based on context. |
| **Selection bubble → "AI" button** | Text selected | Slim bubble: B / I / AI. Clicking AI opens prompt with selection as target. |

Space is intercepted only when the paragraph is completely empty (no text, no whitespace). Normal typing is never affected.

Slash command `/ai` also opens the prompt (existing behavior, kept for discoverability).

### 2. Inline AI Prompt Component

`<InlineAIPrompt>` — a floating input anchored at cursor position. Sparkles icon, text input, close/loading indicator. Below: context-aware preset chips.

**Context-aware modes:**

| Mode | When | Presets | Placeholder |
|------|------|---------|-------------|
| **Generate** | Empty paragraph | "Draft intro", "Continue from above", "Brainstorm", "Outline" | "Ask AI to write..." |
| **Edit** | Cursor in paragraph with text | "Improve", "Simplify", "Fix grammar", "Make shorter", "Make longer", "More formal", "More casual" | "Tell AI what to do with this paragraph..." |
| **Transform** | Text selected | Same as Edit | "Tell AI what to do with selection..." |

- "Continue from above" grabs last ~500 chars and calls `completeText()` (the autocomplete endpoint)
- Freeform instructions accepted in all modes — presets are shortcuts
- Enter submits, Escape closes

### 3. Inline Streaming & Accept/Discard

Core UX change: AI text streams directly into the editor instead of buffering.

**Flow:**
1. User submits instruction
2. Prompt closes
3. Small floating pill: `Sparkles Writing...` (primary color, subtle pulse)
4. Tokens stream into editor at cursor, highlighted with `var(--alfred-accent-subtle)` background
5. On complete, action bar appears below AI block:

```
[ Check Accept ]  [ X Discard ]  [ Retry ]  [ Edit instruction ]
```

**Actions:**
- **Accept** (Tab/Enter): removes highlight, text becomes permanent, cursor at end
- **Discard** (Escape/Cmd+Z): removes AI text, cursor returns to original position
- **Retry**: re-runs same instruction with new generation
- **Edit instruction**: re-opens prompt with previous instruction, discards current result

**Edit mode behavior:** When editing existing text, the original gets strikethrough + dimmed styling while replacement streams below. Accept removes original. Discard restores it.

**Streaming implementation:** New `streamAIToEditor` function uses `streamSSE` directly with per-token callback, inserting via `editor.view.dispatch`. Entire AI insertion is one undoable ProseMirror transaction.

**Abort handling:** An `AbortController` is passed to `streamSSE`. If the user presses Escape during streaming, the fetch is aborted and any partial text is removed (same as Discard). The action bar does not appear — it's a clean cancel.

**Position tracking:** `AiStreamingController` maintains a `{ from, to }` range that updates as tokens are inserted. The action bar anchors to the `to` position. The highlight decoration covers `from..to`.

### 4. Selection Bubble Menu Redesign

**Before:** 8 buttons — B, I, Rewrite, Summarize, Continue, Explain, Research, Ask Alfred

**After:** 3 elements — B, I, Ask AI

```
+----------------------+
|  B   I  |  * Ask AI  |
+----------------------+
```

All specific actions move inside the AI prompt as presets.

**Side panel presets:** Actions that open the AI side panel (Explain, Research, Ask Alfred) get a subtle arrow-out icon to distinguish from inline presets:

```
Inline:  [ Improve ] [ Simplify ] [ Fix grammar ] [ Shorter ] [ Longer ]
Panel:   [ Explain -> ] [ Research -> ] [ Ask Alfred -> ]
```

### 5. Ghost Text & Discoverability

**Empty editor placeholder:**
```
Start writing, or press Space for AI...
```

**Per-paragraph ghost text** (on focused empty paragraphs):
```
Space for AI  ·  / for commands
```

Styled: `font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]` — matches DESIGN.md label aesthetic (JetBrains Mono for meta/labels).

Implementation: TipTap `Placeholder` extension config with function-based placeholder that varies by context.

### 6. Component Architecture

**New files:**

| File | Purpose |
|------|---------|
| `web/components/editor/inline-ai-prompt.tsx` | Floating input, presets, mode detection |
| `web/components/editor/ai-streaming-controller.tsx` | Streaming logic, highlight/action bar state, accept/discard |
| `web/lib/api/ai-stream.ts` | `streamAIToEditor` — wraps `streamSSE` with per-token callback |

**Modified files:**

| File | Changes |
|------|---------|
| `web/components/editor/markdown-notes-editor.tsx` | Remove: bubble menu AI buttons, Cmd+J prompt UI, `handleAiAction`, `openAiPrompt`, `executeAiPrompt`, `closeAiPrompt`, all AI state. Add: Space key handler, slim bubble menu (B/I/AI), mount `<InlineAIPrompt>`. ~400 lines removed, ~50 added. |
| `web/lib/api/ai-assist.ts` | Add `generateText` for empty-line generation |

**Not modified:**
- `shell-store.ts` — side panel presets still use `setAiPanelOpen`
- `agent-invoke.ts` — stays for non-streaming use cases
- Backend — no changes. SSE streaming already works.

**Data flow:**

```
User triggers (Space / Cmd+J / AI button)
  -> MarkdownNotesEditor detects mode (generate/edit/transform)
  -> Opens <InlineAIPrompt> with mode + target text + position
  -> User submits instruction
  -> InlineAIPrompt calls streamAIToEditor()
  -> streamAIToEditor calls streamSSE() with per-token callback
  -> AiStreamingController inserts tokens via editor.view.dispatch()
  -> On complete: shows Accept/Discard action bar
  -> Accept: commit text, remove highlight
  -> Discard: revert to pre-AI state
```

**State management:** All AI state lives inside `<InlineAIPrompt>` and `<AiStreamingController>`. No Zustand store needed. Editor passes ref and trigger events.

## What's NOT in Scope

- **Backend changes** — SSE streaming already works, no new endpoints needed
- **AI side panel redesign** — stays as-is, some presets just open it
- **Slash command menu** — stays as-is (already has AI commands)
- **Real-time collaboration** — would need TipTap extension approach (Approach C), deferred
- **Mobile-specific AI UX** — Space trigger works on mobile keyboards, but no mobile-specific adaptations

## What Already Exists (Reuse)

- `streamSSE()` in `web/lib/api/sse.ts` — SSE streaming with per-token events
- `agentInvoke()` in `web/lib/api/agent-invoke.ts` — intent-based AI calls
- `rewriteText()`, `completeText()`, `summarizeText()` in `web/lib/api/ai-assist.ts`
- `TextAssistService` backend — autocomplete + edit endpoints
- `useShellStore` — side panel open/close
- `useAgentStore` — send messages to AI panel
- TipTap `Placeholder` extension — already configured, needs function-based update
- DESIGN.md label aesthetic — JetBrains Mono, uppercase, tracked, tertiary color
