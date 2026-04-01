# Notion-Style Inline AI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the notes editor's scattered AI features (selection bubble menu, Cmd+J prompt, slash commands) with a unified Notion AI-style experience — Space on empty line triggers AI, tokens stream inline, one prompt component handles all AI interactions.

**Architecture:** Extract all AI interaction from `markdown-notes-editor.tsx` into two new components: `<InlineAIPrompt>` (floating input + presets) and `<AiStreamingController>` (streaming + accept/discard). A new `ai-stream.ts` module wraps the existing `streamSSE` with per-token callbacks instead of buffering. The editor becomes a thin shell that detects triggers and delegates to these components.

**Tech Stack:** TipTap/ProseMirror (editor), React 19, existing `streamSSE` for SSE, existing backend agent endpoints (no backend changes).

**Spec:** `.claude/docs/2026-03-31-notion-style-inline-ai-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `web/lib/api/ai-stream.ts` | Create | `streamAIInline()` — SSE streaming with per-token callback + AbortController |
| `web/lib/api/ai-assist.ts` | Modify | Add `generateText()` for empty-line AI generation |
| `web/components/editor/inline-ai-prompt.tsx` | Create | Floating AI prompt input, context-aware presets, mode detection |
| `web/components/editor/ai-streaming-controller.tsx` | Create | Token insertion, highlight decoration, accept/discard action bar |
| `web/components/editor/markdown-notes-editor.tsx` | Modify | Remove old AI UI (~400 lines), add Space handler, slim bubble menu, mount new components |

---

### Task 1: Streaming API Layer (`ai-stream.ts`)

**Files:**
- Create: `web/lib/api/ai-stream.ts`
- Reference: `web/lib/api/sse.ts` (existing `streamSSE`)
- Reference: `web/lib/api/ai-assist.ts` (existing intent patterns)
- Reference: `web/lib/api/routes.ts:93` (agent stream endpoint)

- [ ] **Step 1: Create `ai-stream.ts` with `streamAIInline` function**

This wraps `streamSSE` but exposes a per-token callback instead of buffering the full response. It also accepts an `AbortController` for cancellation.

```typescript
// web/lib/api/ai-stream.ts
import { apiRoutes } from "@/lib/api/routes";
import { streamSSE } from "@/lib/api/sse";

export type StreamAIOptions = {
  intent: "autocomplete" | "edit_text" | "summarize" | "generate";
  intentArgs: Record<string, unknown>;
  onToken: (token: string) => void;
  onComplete: () => void;
  onError: (error: Error) => void;
  signal?: AbortSignal;
  model?: string;
};

export async function streamAIInline(opts: StreamAIOptions): Promise<void> {
  const { intent, intentArgs, onToken, onComplete, onError, signal, model } = opts;

  try {
    await streamSSE(
      apiRoutes.agent.stream,
      {
        message: "",
        intent,
        intent_args: intentArgs,
        model: model ?? "gpt-4.1-mini",
      },
      (event, data) => {
        if (event === "token" && typeof data.content === "string") {
          onToken(data.content);
        }
        if (event === "error" && typeof data.message === "string") {
          onError(new Error(data.message));
        }
      },
      signal,
    );
    onComplete();
  } catch (err) {
    if (signal?.aborted) return; // Clean abort, not an error
    onError(err instanceof Error ? err : new Error("AI streaming failed"));
  }
}
```

- [ ] **Step 2: Add `generateText` to `ai-assist.ts`**

This is the intent for empty-line generation (user types "Write an intro about X").

```typescript
// Add to web/lib/api/ai-assist.ts, after the existing functions:

export async function generateText(
  instruction: string,
  contextAbove = "",
): Promise<string> {
  return agentInvoke({
    intent: "edit_text",
    intentArgs: {
      text: contextAbove.slice(-1000),
      instruction: `Generate new content: ${instruction}`,
    },
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add web/lib/api/ai-stream.ts web/lib/api/ai-assist.ts
git commit -m "feat(editor): add streaming AI layer and generateText helper"
```

---

### Task 2: Inline AI Prompt Component (`inline-ai-prompt.tsx`)

**Files:**
- Create: `web/components/editor/inline-ai-prompt.tsx`
- Reference: `web/components/editor/markdown-notes-editor.tsx:952-1019` (current Cmd+J prompt to replicate and improve)
- Reference: `web/lib/stores/shell-store.ts` (for side-panel presets)
- Reference: `web/lib/stores/agent-store.ts` (for Ask Alfred preset)

- [ ] **Step 1: Create `inline-ai-prompt.tsx` with types and mode detection**

```typescript
// web/components/editor/inline-ai-prompt.tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { type Editor } from "@tiptap/react";
import { ExternalLink, Loader2, Sparkles, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useShellStore } from "@/lib/stores/shell-store";
import { useAgentStore } from "@/lib/stores/agent-store";

export type AIPromptMode = "generate" | "edit" | "transform";

export type InlineAIPromptProps = {
  editor: Editor;
  mode: AIPromptMode;
  /** Position to anchor the floating prompt */
  position: { top: number; left: number };
  /** Text the AI will operate on (empty string for generate mode) */
  targetText: string;
  /** ProseMirror range of the target text */
  targetRange: { from: number; to: number } | null;
  /** Called when user submits an instruction */
  onSubmit: (instruction: string, preset?: string) => void;
  /** Called when user closes the prompt */
  onClose: () => void;
  /** Whether AI is currently streaming */
  isStreaming: boolean;
};

type Preset = {
  label: string;
  instruction: string;
  /** If true, opens the AI side panel instead of inline streaming */
  panel?: boolean;
};

const GENERATE_PRESETS: Preset[] = [
  { label: "Draft intro", instruction: "Write an engaging introduction for this section" },
  { label: "Continue from above", instruction: "__CONTINUE__" },
  { label: "Brainstorm", instruction: "Brainstorm ideas and list them as bullet points" },
  { label: "Outline", instruction: "Create a structured outline for this topic" },
];

const EDIT_PRESETS: Preset[] = [
  { label: "Improve", instruction: "Improve clarity and grammar" },
  { label: "Simplify", instruction: "Simplify this text — use shorter sentences and simpler words" },
  { label: "Fix grammar", instruction: "Fix any grammar and spelling mistakes, keep the same tone" },
  { label: "Make shorter", instruction: "Make this more concise without losing meaning" },
  { label: "Make longer", instruction: "Expand this with more detail and explanation" },
  { label: "More formal", instruction: "Rewrite in a more professional, formal tone" },
  { label: "More casual", instruction: "Rewrite in a more casual, conversational tone" },
];

const PANEL_PRESETS: Preset[] = [
  { label: "Explain", instruction: "Explain this in simpler terms", panel: true },
  { label: "Research", instruction: "Research this topic in my knowledge base", panel: true },
  { label: "Ask Alfred", instruction: "", panel: true },
];

function presetsForMode(mode: AIPromptMode): Preset[] {
  if (mode === "generate") return GENERATE_PRESETS;
  return [...EDIT_PRESETS, ...PANEL_PRESETS];
}

function placeholderForMode(mode: AIPromptMode): string {
  if (mode === "generate") return "Ask AI to write...";
  if (mode === "edit") return "Tell AI what to do with this paragraph...";
  return "Tell AI what to do with selection...";
}
```

- [ ] **Step 2: Add the component body with input, presets, and keyboard handling**

```typescript
// Continue in inline-ai-prompt.tsx — the exported component:

export function InlineAIPrompt({
  editor,
  mode,
  position,
  targetText,
  targetRange,
  onSubmit,
  onClose,
  isStreaming,
}: InlineAIPromptProps) {
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const presets = presetsForMode(mode);

  // Auto-focus on mount
  useEffect(() => {
    const timer = setTimeout(() => inputRef.current?.focus(), 50);
    return () => clearTimeout(timer);
  }, []);

  // Close on click outside
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const el = (e.target as HTMLElement).closest("[data-ai-prompt]");
      if (!el) onClose();
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  const handlePreset = useCallback(
    (preset: Preset) => {
      if (preset.panel) {
        // Open AI side panel
        useShellStore.getState().setAiPanelOpen(true);
        if (preset.instruction && targetText) {
          void useAgentStore
            .getState()
            .sendMessage(`${preset.instruction}:\n\n${targetText}`);
        } else {
          // "Ask Alfred" — just focus the panel input
          setTimeout(() => {
            const panelInput = document.querySelector<HTMLTextAreaElement>(
              '[aria-label="AI Assistant"] textarea',
            );
            if (panelInput) {
              panelInput.focus();
              if (targetText) {
                panelInput.value = targetText;
                panelInput.dispatchEvent(new Event("input", { bubbles: true }));
              }
            }
          }, 250);
        }
        onClose();
        return;
      }
      onSubmit(preset.instruction, preset.label);
    },
    [targetText, onSubmit, onClose],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && input.trim() && !isStreaming) {
        e.preventDefault();
        onSubmit(input.trim());
      }
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    },
    [input, isStreaming, onSubmit, onClose],
  );

  return (
    <div
      data-ai-prompt
      className="fixed z-50 w-[420px] overflow-hidden rounded-lg border bg-card shadow-xl animate-in fade-in slide-in-from-top-1 duration-150"
      style={{ top: `${position.top}px`, left: `${position.left}px` }}
    >
      {/* Input row */}
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <Sparkles className="h-3.5 w-3.5 shrink-0 text-primary" />
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholderForMode(mode)}
          className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
          disabled={isStreaming}
        />
        {isStreaming ? (
          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
        ) : (
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 text-muted-foreground hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Presets */}
      {!isStreaming && (
        <div className="flex flex-wrap gap-1.5 px-3 py-2">
          {presets.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                handlePreset(preset);
              }}
              className={cn(
                "rounded-md border border-border/50 bg-secondary/50 px-2 py-1",
                "font-mono text-[10px] uppercase tracking-wider text-muted-foreground",
                "transition-colors hover:border-primary/30 hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
                "inline-flex items-center gap-1",
              )}
            >
              {preset.label}
              {preset.panel && <ExternalLink className="h-2.5 w-2.5" />}
            </button>
          ))}
        </div>
      )}

      {/* Status bar */}
      <div className="border-t px-3 py-1.5">
        <span className="font-mono text-[9px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
          {mode === "generate"
            ? "Generate new content"
            : `Editing ${targetText.length} chars`}
          {" · "}Enter to apply · Esc to cancel
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add web/components/editor/inline-ai-prompt.tsx
git commit -m "feat(editor): add InlineAIPrompt component with mode-aware presets"
```

---

### Task 3: AI Streaming Controller (`ai-streaming-controller.tsx`)

**Files:**
- Create: `web/components/editor/ai-streaming-controller.tsx`
- Reference: `web/lib/api/ai-stream.ts` (from Task 1)
- Reference: `web/lib/api/ai-assist.ts` (for `completeText` used by "Continue from above")

- [ ] **Step 1: Create the controller with streaming state management**

```typescript
// web/components/editor/ai-streaming-controller.tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { type Editor } from "@tiptap/react";
import { Check, Loader2, Pencil, RotateCcw, Sparkles, X } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { streamAIInline } from "@/lib/api/ai-stream";
import { completeText } from "@/lib/api/ai-assist";

export type StreamingState =
  | { status: "idle" }
  | { status: "streaming"; instruction: string }
  | { status: "done"; instruction: string };

export type AiStreamingControllerProps = {
  editor: Editor;
  state: StreamingState;
  /** Where to insert generated text */
  insertAt: number;
  /** Original text range being edited (null for generate mode) */
  originalRange: { from: number; to: number; text: string } | null;
  /** Called when streaming completes or user accepts/discards */
  onFinish: (action: "accept" | "discard") => void;
  /** Called when user wants to retry or edit instruction */
  onRetry: () => void;
  onEditInstruction: (previousInstruction: string) => void;
};

export function AiStreamingController({
  editor,
  state,
  insertAt,
  originalRange,
  onFinish,
  onRetry,
  onEditInstruction,
}: AiStreamingControllerProps) {
  const abortRef = useRef<AbortController | null>(null);
  const insertRangeRef = useRef<{ from: number; to: number }>({
    from: insertAt,
    to: insertAt,
  });
  const [actionBarPosition, setActionBarPosition] = useState<{
    top: number;
    left: number;
  } | null>(null);

  // Stream tokens into editor
  const startStreaming = useCallback(
    async (instruction: string) => {
      if (!editor || editor.isDestroyed) return;

      const abort = new AbortController();
      abortRef.current = abort;

      // For "Continue from above", use completeText which is purpose-built
      if (instruction === "__CONTINUE__") {
        try {
          const textAbove = editor.state.doc.textBetween(
            0,
            insertAt,
            "\n",
          );
          const result = await completeText(
            textAbove.slice(-500),
            textAbove.slice(-1000, -500),
            "",
          );
          if (abort.signal.aborted || editor.isDestroyed) return;
          editor.view.dispatch(
            editor.state.tr.insertText(result, insertAt),
          );
          insertRangeRef.current = {
            from: insertAt,
            to: insertAt + result.length,
          };
          updateActionBarPosition();
        } catch (err) {
          if (!abort.signal.aborted) {
            toast.error(
              err instanceof Error ? err.message : "AI failed",
            );
            onFinish("discard");
          }
        }
        return;
      }

      // Determine intent based on whether we're editing or generating
      const isEditing = originalRange !== null;
      const intent = isEditing ? "edit_text" : "edit_text";
      const intentArgs = isEditing
        ? { text: originalRange.text, instruction }
        : {
            text: editor.state.doc
              .textBetween(
                Math.max(0, insertAt - 1000),
                insertAt,
                "\n",
              )
              .slice(-1000),
            instruction: `Generate new content: ${instruction}`,
          };

      let currentPos = insertAt;

      await streamAIInline({
        intent,
        intentArgs,
        onToken: (token) => {
          if (editor.isDestroyed) return;
          editor.view.dispatch(
            editor.state.tr.insertText(token, currentPos),
          );
          currentPos += token.length;
          insertRangeRef.current = {
            from: insertAt,
            to: currentPos,
          };
        },
        onComplete: () => {
          updateActionBarPosition();
        },
        onError: (err) => {
          toast.error(err.message);
          discardInserted();
          onFinish("discard");
        },
        signal: abort.signal,
      });
    },
    [editor, insertAt, originalRange, onFinish],
  );

  const updateActionBarPosition = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    const { to } = insertRangeRef.current;
    try {
      const coords = editor.view.coordsAtPos(
        Math.min(to, editor.state.doc.content.size),
      );
      setActionBarPosition({ top: coords.bottom + 8, left: coords.left });
    } catch {
      // Position might be out of range during rapid updates
    }
  }, [editor]);

  const discardInserted = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    const { from, to } = insertRangeRef.current;
    if (to > from) {
      editor.view.dispatch(editor.state.tr.delete(from, to));
    }
    // If we were editing, the original text is still there (we inserted below it)
    // so no restoration needed
  }, [editor]);

  const handleAccept = useCallback(() => {
    // If editing existing text, remove the original
    if (originalRange) {
      // Original text is still at its original position, AI text is after it
      // We need to remove the original range
      const { from, to } = originalRange;
      if (!editor.isDestroyed) {
        editor.view.dispatch(editor.state.tr.delete(from, to));
        // Adjust our insert range since we deleted before it
        const deleted = to - from;
        insertRangeRef.current = {
          from: insertRangeRef.current.from - deleted,
          to: insertRangeRef.current.to - deleted,
        };
      }
    }
    onFinish("accept");
    toast.success(originalRange ? "AI edit applied" : "AI text inserted");
  }, [editor, originalRange, onFinish]);

  const handleDiscard = useCallback(() => {
    abortRef.current?.abort();
    discardInserted();
    onFinish("discard");
  }, [discardInserted, onFinish]);

  // Start streaming when state changes to "streaming"
  useEffect(() => {
    if (state.status === "streaming") {
      void startStreaming(state.instruction);
    }
    return () => {
      abortRef.current?.abort();
    };
  }, [state, startStreaming]);

  // Keyboard shortcuts for action bar
  useEffect(() => {
    if (state.status !== "done") return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Tab" || e.key === "Enter") {
        e.preventDefault();
        handleAccept();
      }
      if (e.key === "Escape") {
        e.preventDefault();
        handleDiscard();
      }
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [state.status, handleAccept, handleDiscard]);

  // Streaming indicator pill
  if (state.status === "streaming") {
    const coords = (() => {
      try {
        return editor.view.coordsAtPos(
          Math.min(
            insertRangeRef.current.to,
            editor.state.doc.content.size,
          ),
        );
      } catch {
        return null;
      }
    })();

    return coords ? (
      <div
        className="fixed z-50 flex items-center gap-1.5 rounded-full border bg-card px-3 py-1 shadow-md"
        style={{
          top: `${coords.bottom + 8}px`,
          left: `${coords.left}px`,
        }}
      >
        <Sparkles className="h-3 w-3 animate-pulse text-primary" />
        <span className="font-mono text-[10px] uppercase tracking-wider text-primary">
          Writing...
        </span>
      </div>
    ) : null;
  }

  // Accept/Discard action bar
  if (state.status === "done" && actionBarPosition) {
    return (
      <div
        className="fixed z-50 flex items-center gap-1 rounded-md border bg-card p-1 shadow-lg animate-in fade-in zoom-in-95 duration-100"
        style={{
          top: `${actionBarPosition.top}px`,
          left: `${actionBarPosition.left}px`,
        }}
      >
        <button
          type="button"
          onClick={handleAccept}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-2.5 py-1.5",
            "bg-primary text-primary-foreground",
            "font-mono text-[10px] uppercase tracking-wider",
            "hover:bg-primary/90 transition-colors",
          )}
        >
          <Check className="h-3 w-3" />
          Accept
        </button>
        <button
          type="button"
          onClick={handleDiscard}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-2.5 py-1.5",
            "text-muted-foreground",
            "font-mono text-[10px] uppercase tracking-wider",
            "hover:bg-secondary hover:text-foreground transition-colors",
          )}
        >
          <X className="h-3 w-3" />
          Discard
        </button>
        <button
          type="button"
          onClick={onRetry}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-2.5 py-1.5",
            "text-muted-foreground",
            "font-mono text-[10px] uppercase tracking-wider",
            "hover:bg-secondary hover:text-foreground transition-colors",
          )}
        >
          <RotateCcw className="h-3 w-3" />
          Retry
        </button>
        <button
          type="button"
          onClick={() => onEditInstruction(state.instruction)}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-2.5 py-1.5",
            "text-muted-foreground",
            "font-mono text-[10px] uppercase tracking-wider",
            "hover:bg-secondary hover:text-foreground transition-colors",
          )}
        >
          <Pencil className="h-3 w-3" />
          Edit
        </button>
      </div>
    );
  }

  return null;
}
```

- [ ] **Step 2: Commit**

```bash
git add web/components/editor/ai-streaming-controller.tsx
git commit -m "feat(editor): add AiStreamingController with streaming + accept/discard"
```

---

### Task 4: Refactor Editor — Remove Old AI UI, Add Triggers

**Files:**
- Modify: `web/components/editor/markdown-notes-editor.tsx`
- Reference: `web/components/editor/inline-ai-prompt.tsx` (from Task 2)
- Reference: `web/components/editor/ai-streaming-controller.tsx` (from Task 3)

This is the biggest task — gutting the old AI UI and wiring in the new components. Broken into clear sub-steps.

- [ ] **Step 1: Remove old AI imports and state**

In `markdown-notes-editor.tsx`, remove these imports (line 22):
```
BookOpen, FileText, Loader2, MessageCircle, PenLine, Search, Sparkles, Wand2, X
```

Replace with:
```
Bold, Italic, Loader2, Sparkles
```

Remove these imports (lines 25-27):
```
import { completeText, rewriteText, summarizeText } from "@/lib/api/ai-assist";
import { useShellStore } from "@/lib/stores/shell-store";
import { useAgentStore } from "@/lib/stores/agent-store";
```

Add new imports:
```typescript
import { InlineAIPrompt, type AIPromptMode } from "@/components/editor/inline-ai-prompt";
import { AiStreamingController, type StreamingState } from "@/components/editor/ai-streaming-controller";
```

Remove these state declarations (lines 88-105 area):
```
const [aiLoading, setAiLoading] = useState<...>(null);
const [aiPromptOpen, setAiPromptOpen] = useState(false);
const [aiPromptPosition, setAiPromptPosition] = useState<...>(null);
const [aiPromptInput, setAiPromptInput] = useState("");
const [aiPromptLoading, setAiPromptLoading] = useState(false);
const aiPromptRef = useRef<HTMLInputElement>(null);
const aiPromptTargetRef = useRef<...>(null);
```

Add new state:
```typescript
// Inline AI state
const [aiPromptOpen, setAiPromptOpen] = useState(false);
const [aiPromptMode, setAiPromptMode] = useState<AIPromptMode>("generate");
const [aiPromptPosition, setAiPromptPosition] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
const [aiTargetText, setAiTargetText] = useState("");
const [aiTargetRange, setAiTargetRange] = useState<{ from: number; to: number } | null>(null);
const [streamingState, setStreamingState] = useState<StreamingState>({ status: "idle" });
const [streamInsertAt, setStreamInsertAt] = useState(0);
const [streamOriginalRange, setStreamOriginalRange] = useState<{ from: number; to: number; text: string } | null>(null);
```

- [ ] **Step 2: Remove old AI functions**

Delete these functions entirely:
- `handleAiAction` (lines 618-659)
- `openAiPrompt` (lines 662-697)
- `executeAiPrompt` (lines 699-721)
- `closeAiPrompt` (lines 723-729)

Add the new unified trigger function:
```typescript
const openAI = useCallback(
  (ed: Editor, modeOverride?: AIPromptMode) => {
    const { from, to } = ed.state.selection;
    const hasSelection = !ed.state.selection.empty;
    const { $from } = ed.state.selection;
    const paragraphText = $from.parent.textContent;

    let mode: AIPromptMode;
    let targetText: string;
    let targetRange: { from: number; to: number } | null;

    if (modeOverride) {
      mode = modeOverride;
    } else if (hasSelection) {
      mode = "transform";
    } else if (!paragraphText.trim()) {
      mode = "generate";
    } else {
      mode = "edit";
    }

    if (mode === "transform") {
      targetText = ed.state.doc.textBetween(from, to, " ");
      targetRange = { from, to };
    } else if (mode === "edit") {
      targetText = paragraphText;
      targetRange = { from: $from.start(), to: $from.end() };
    } else {
      targetText = "";
      targetRange = null;
    }

    const coords = ed.view.coordsAtPos(from);
    setAiPromptMode(mode);
    setAiTargetText(targetText);
    setAiTargetRange(targetRange);
    setAiPromptPosition({ top: coords.bottom + 8, left: coords.left });
    setAiPromptOpen(true);
  },
  [],
);

const handleAISubmit = useCallback(
  (instruction: string) => {
    setAiPromptOpen(false);
    const insertPos = aiTargetRange
      ? aiTargetRange.to // Insert after the target text (edit/transform)
      : editor?.state.selection.from ?? 0; // Insert at cursor (generate)
    setStreamInsertAt(insertPos);
    setStreamOriginalRange(
      aiTargetRange && aiTargetText
        ? { from: aiTargetRange.from, to: aiTargetRange.to, text: aiTargetText }
        : null,
    );
    setStreamingState({ status: "streaming", instruction });
  },
  [editor, aiTargetRange, aiTargetText],
);

const handleStreamFinish = useCallback(
  (_action: "accept" | "discard") => {
    setStreamingState({ status: "idle" });
    setStreamOriginalRange(null);
    editor?.commands.focus();
  },
  [editor],
);

const handleStreamRetry = useCallback(() => {
  if (streamingState.status === "done") {
    setStreamingState({ status: "streaming", instruction: streamingState.instruction });
  }
}, [streamingState]);

const handleEditInstruction = useCallback(
  (prev: string) => {
    // Re-open prompt with previous instruction context
    if (!editor) return;
    openAI(editor);
  },
  [editor, openAI],
);
```

- [ ] **Step 3: Update keyboard handler — add Space trigger, update Cmd+J**

In the `onKeyDown` handler inside the `useEffect` (around line 499-566), replace the Cmd+J block:

```typescript
// Replace the Cmd+J handler:
if (isMod && key === "j") {
  event.preventDefault();
  openAI(editor);
  return;
}
```

Add Space trigger before the slash command check:

```typescript
// Space on empty paragraph — open AI prompt in generate mode
if (event.key === " " && !isMod && !event.shiftKey) {
  const { $from } = editor.state.selection;
  const parent = $from.parent;
  if (
    parent.type.name === "paragraph" &&
    parent.textContent === "" &&
    editor.state.selection.empty
  ) {
    event.preventDefault();
    openAI(editor, "generate");
    return;
  }
}
```

- [ ] **Step 4: Update the slash command `/ai` to use `openAI`**

Replace the "AI Edit" slash command (around line 249-256):
```typescript
{
  title: "AI Edit",
  description: "Edit current paragraph with AI (⌘J)",
  keywords: ["ai", "edit", "rewrite", "improve", "fix"],
  run: (ed) => {
    openAI(ed);
  },
},
```

- [ ] **Step 5: Replace the bubble menu JSX**

Delete the entire AI bubble menu block (lines 811-949) and replace with the slim version:

```tsx
{/* Slim bubble menu — B / I / AI */}
{menuPosition && !editor.state.selection.empty && (
  <div
    className="fixed z-50 flex items-center gap-0.5 rounded-md border bg-card p-1 shadow-lg animate-in fade-in zoom-in-95 duration-100"
    style={{
      top: `${menuPosition.top}px`,
      left: `${menuPosition.left}px`,
      transform: "translateX(-50%)",
    }}
  >
    <Button
      variant="ghost"
      size="sm"
      onClick={() => editor.chain().focus().toggleBold().run()}
      className={cn(
        "h-7 w-7 p-0",
        editor.isActive("bold") && "bg-[var(--alfred-accent-subtle)] text-primary",
      )}
    >
      <Bold className="h-3.5 w-3.5" />
    </Button>
    <Button
      variant="ghost"
      size="sm"
      onClick={() => editor.chain().focus().toggleItalic().run()}
      className={cn(
        "h-7 w-7 p-0",
        editor.isActive("italic") && "bg-[var(--alfred-accent-subtle)] text-primary",
      )}
    >
      <Italic className="h-3.5 w-3.5" />
    </Button>

    <div className="mx-1 h-4 w-px bg-border" />

    <Button
      variant="ghost"
      size="sm"
      className="h-7 gap-1.5 px-2 font-medium text-[10px] uppercase tracking-wider text-primary hover:bg-[var(--alfred-accent-subtle)]"
      onClick={() => openAI(editor, "transform")}
    >
      <Sparkles className="h-3 w-3" />
      Ask AI
    </Button>
  </div>
)}
```

- [ ] **Step 6: Remove old Cmd+J prompt JSX, mount new components**

Delete the entire `{/* Inline AI prompt — Cmd+J */}` block (lines 952-1019).

Add the new components before the editor content div:

```tsx
{/* Inline AI Prompt */}
{aiPromptOpen && (
  <InlineAIPrompt
    editor={editor}
    mode={aiPromptMode}
    position={aiPromptPosition}
    targetText={aiTargetText}
    targetRange={aiTargetRange}
    onSubmit={handleAISubmit}
    onClose={() => {
      setAiPromptOpen(false);
      editor.commands.focus();
    }}
    isStreaming={streamingState.status === "streaming"}
  />
)}

{/* AI Streaming Controller */}
{streamingState.status !== "idle" && (
  <AiStreamingController
    editor={editor}
    state={streamingState}
    insertAt={streamInsertAt}
    originalRange={streamOriginalRange}
    onFinish={handleStreamFinish}
    onRetry={handleStreamRetry}
    onEditInstruction={handleEditInstruction}
  />
)}
```

- [ ] **Step 7: Commit**

```bash
git add web/components/editor/markdown-notes-editor.tsx
git commit -m "refactor(editor): replace old AI UI with unified InlineAIPrompt + streaming"
```

---

### Task 5: Ghost Text & Placeholder Updates

**Files:**
- Modify: `web/components/editor/markdown-notes-editor.tsx` (Placeholder extension config)

- [ ] **Step 1: Update the Placeholder extension config**

In the `extensions` useMemo (around line 129-132), replace the Placeholder config:

```typescript
Placeholder.configure({
  placeholder: ({ node, editor: ed }) => {
    // First paragraph when editor is empty
    if (
      ed.isEmpty &&
      node.type.name === "paragraph"
    ) {
      return placeholder ?? "Start writing, or press Space for AI...";
    }
    // Any other empty paragraph
    if (node.type.name === "paragraph" && node.textContent === "") {
      return "Space for AI  ·  / for commands";
    }
    return "";
  },
  emptyEditorClass: "is-editor-empty",
}),
```

- [ ] **Step 2: Add CSS for ghost text styling**

The TipTap placeholder uses the `.is-empty::before` pseudo-element. We need to make sure the per-paragraph ghost text gets the JetBrains Mono label styling. Check if the existing `globals.css` already has placeholder styles, and if so, update them.

Look for existing placeholder styles in `web/app/globals.css` or the editor prose classes. Add/update:

```css
/* In globals.css or a scoped editor stylesheet */
.ProseMirror p.is-empty:not(.is-editor-empty)::before {
  font-family: var(--font-mono);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--alfred-text-tertiary);
}
```

- [ ] **Step 3: Commit**

```bash
git add web/components/editor/markdown-notes-editor.tsx web/app/globals.css
git commit -m "feat(editor): add Notion-style ghost text placeholders for AI discoverability"
```

---

### Task 6: Clean Up Unused Slash Commands

**Files:**
- Modify: `web/components/editor/markdown-notes-editor.tsx` (slash command definitions)

- [ ] **Step 1: Remove redundant AI slash commands**

The following slash commands are now handled by the InlineAIPrompt presets and can be removed from the `slashCommands` array. Keep only "AI Edit" (which calls `openAI`) and "Ask Alfred" (which opens the side panel). Remove:

- "Generate" (lines 252-266) — replaced by Space trigger + "Draft intro" preset
- "Research" (lines 268-283) — replaced by "Research" panel preset
- "Summarize above" (lines 284-298) — can be done via freeform instruction in the prompt
- "Translate" (lines 300-316) — can be done via freeform instruction in the prompt

Keep:
- "AI Edit" — entry point to the unified prompt
- "Ask Alfred" — direct route to side panel (power users expect this)

- [ ] **Step 2: Commit**

```bash
git add web/components/editor/markdown-notes-editor.tsx
git commit -m "refactor(editor): remove redundant AI slash commands consolidated into InlineAIPrompt"
```

---

### Task 7: Smoke Test & Polish

**Files:**
- All files from Tasks 1-6

- [ ] **Step 1: Verify the app compiles**

```bash
cd web && npx next build 2>&1 | tail -20
```

Expected: Build succeeds with no type errors related to the new components.

- [ ] **Step 2: Manual smoke test checklist**

Run `cd web && npm run dev` and test each trigger:

1. Open a note in the editor
2. Click into an empty paragraph → press Space → AI prompt opens in Generate mode with "Ask AI to write..." placeholder
3. Press Escape → prompt closes, Space works normally for typing
4. Type some text → select it → bubble menu shows B / I / Ask AI only
5. Click "Ask AI" → prompt opens in Transform mode with selection as target
6. Press Cmd+J on a paragraph with text → prompt opens in Edit mode
7. Press Cmd+J on an empty paragraph → prompt opens in Generate mode
8. Submit an instruction → prompt closes, "Writing..." pill appears, text streams in
9. After streaming → Accept/Discard bar appears
10. Press Tab → text accepted, highlight removed
11. Undo (Cmd+Z) after accepting to verify undo still works

- [ ] **Step 3: Fix any type errors or runtime issues discovered**

Address specific issues found during smoke test.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "fix(editor): polish inline AI prompt after smoke testing"
```
