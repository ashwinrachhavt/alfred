"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Transaction } from "@tiptap/pm/state";
import { type Editor } from "@tiptap/react";
import { toast } from "sonner";
import { Check, Pencil, Sparkles, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { ALFRED_AI_STREAM_META } from "@/components/editor/editor-transaction-meta";
import { streamWritingCompose } from "@/lib/api/writing-stream";
import {
  FOLLOWUPS,
  primaryFollowups,
  resolveFollowup,
  type FollowupDef,
} from "@/lib/notes-ai/followups";
import {
  normalizeTiptapRange,
  remapTiptapRange,
  type TiptapRange,
} from "@/lib/utils/tiptap-ranges";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type StreamingState =
  | { status: "idle" }
  | { status: "streaming"; instruction: string }
  | { status: "done"; instruction: string };

export type AiStreamingControllerProps = {
  editor: Editor;
  state: StreamingState;
  insertAt: number;
  originalRange: { from: number; to: number; text: string } | null;
  documentTitle?: string;
  documentId?: string | null;
  onFinish: (action: "accept" | "discard") => void;
  onStreamComplete: () => void;
  /**
   * Re-enter streaming with a new instruction. Used by every follow-up —
   * Try again, Make longer, Continue writing, Change tone, etc.
   *
   * The controller has already mutated the doc (deleting prior AI text for
   * `rewrite` mode follow-ups, or leaving it in place for `extend` mode)
   * before this fires, so the parent only needs to flip state back to
   * `streaming` with the new instruction.
   */
  onFollowup: (instruction: string) => void;
  onEditInstruction: (previousInstruction: string) => void;
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function AiStreamingController({
  editor,
  state,
  insertAt,
  originalRange,
  documentTitle,
  documentId,
  onFinish,
  onStreamComplete,
  onFollowup,
  onEditInstruction,
}: AiStreamingControllerProps) {
  const abortRef = useRef<AbortController | null>(null);
  const tokenBufferRef = useRef("");
  const tokenFrameRef = useRef<number | null>(null);
  // Full markdown accumulated for the *current* AI message. Captured as
  // tokens arrive so we can replay it through the markdown parser on
  // MESSAGE_END, when the streamed plain text is replaced with properly
  // rendered nodes (headings, lists, bold, etc).
  const markdownBufferRef = useRef("");
  // Last fully-streamed message content. Used by follow-ups (Make longer,
  // Continue writing, Change tone) as the prior output to feed back into
  // the next instruction. Stays valid until accept/discard.
  const lastOutputRef = useRef("");
  // Set by handleFollowup just before re-entering streaming state. Tells
  // the streaming useEffect to skip the initial insertAt reset so the
  // pre-positioned insertRangeRef (already adjusted by handleFollowup) is
  // honored. Cleared once the new stream begins.
  const isFollowupRef = useRef(false);
  const insertRangeRef = useRef<TiptapRange>({
    from: insertAt,
    to: insertAt,
  });
  const originalRangeRef = useRef<typeof originalRange>(originalRange);

  const [pillPos, setPillPos] = useState<{ top: number; left: number } | null>(null);
  const [actionBarPos, setActionBarPos] = useState<{
    top: number;
    left: number;
  } | null>(null);
  // Whether the "More" overflow menu (tone/translate/transform variants)
  // is open below the primary action chip row.
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const [activeSubmenu, setActiveSubmenu] = useState<"tone" | "translate" | null>(null);

  const clipMiddle = useCallback((text: string, maxChars: number) => {
    if (text.length <= maxChars) return text.trim();
    const head = text.slice(0, Math.floor(maxChars * 0.55)).trim();
    const tail = text.slice(-Math.floor(maxChars * 0.3)).trim();
    return `${head}\n\n[...]\n\n${tail}`.trim();
  }, []);

  const buildWritingContext = useCallback(() => {
    const docSize = editor.state.doc.content.size;
    const contextFrom = originalRange?.from ?? insertAt;
    const contextTo = originalRange?.to ?? insertAt;
    const localWindow = 2200;
    const fullDocument = editor.state.doc.textBetween(0, docSize, "\n").trim();
    const before = editor.state.doc
      .textBetween(Math.max(0, contextFrom - localWindow), contextFrom, "\n")
      .trim();
    const after = editor.state.doc
      .textBetween(contextTo, Math.min(docSize, contextTo + localWindow), "\n")
      .trim();

    const noteOverviewParts = [
      documentTitle ? `Note title: ${documentTitle}` : "",
      fullDocument ? `Note overview:\n${clipMiddle(fullDocument, 4200)}` : "",
      before ? `Context before cursor:\n${before.slice(-1400)}` : "",
      after ? `Context after cursor:\n${after.slice(0, 1400)}` : "",
    ].filter(Boolean);

    const localFocus = [
      before ? `Before cursor:\n${before.slice(-1800)}` : "",
      originalRange?.text ? `Selected text:\n${originalRange.text}` : "",
      after ? `After cursor:\n${after.slice(0, 1800)}` : "",
    ]
      .filter(Boolean)
      .join("\n\n");

    return {
      draftExcerpt: clipMiddle(localFocus || fullDocument, 5200),
      pageText: noteOverviewParts.join("\n\n"),
    };
  }, [clipMiddle, documentTitle, editor, insertAt, originalRange]);

  const resolveInstruction = useCallback((instruction: string) => {
    if (instruction === "__CONTINUE__") {
      return "Continue this note naturally from the cursor. Match the existing voice, level of detail, and structure. Do not repeat what is already written, and do not add filler.";
    }
    return instruction;
  }, []);

  /* ---- helpers --------------------------------------------------- */

  const updateActionBarPosition = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    try {
      const { to } = normalizeTiptapRange(insertRangeRef.current, editor.state.doc.content.size);
      const coords = editor.view.coordsAtPos(to);
      setActionBarPos({ top: coords.bottom + 8, left: coords.left });
    } catch {
      // coordsAtPos can throw if the position is out of range
    }
  }, [editor]);

  const updatePillPosition = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    try {
      const { to } = normalizeTiptapRange(insertRangeRef.current, editor.state.doc.content.size);
      const coords = editor.view.coordsAtPos(to);
      setPillPos({ top: coords.bottom + 8, left: coords.left });
    } catch {
      // ignore
    }
  }, [editor]);

  const discardInserted = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    const { from, to } = normalizeTiptapRange(
      insertRangeRef.current,
      editor.state.doc.content.size,
    );
    if (from < to) {
      const tr = editor.state.tr.delete(from, to).setMeta(ALFRED_AI_STREAM_META, true);
      editor.view.dispatch(tr);
    }
    insertRangeRef.current = { from, to: from };
    setPillPos(null);
    setActionBarPos(null);
  }, [editor]);

  const flushTokenBuffer = useCallback(() => {
    if (tokenFrameRef.current !== null) {
      window.cancelAnimationFrame(tokenFrameRef.current);
      tokenFrameRef.current = null;
    }

    const text = tokenBufferRef.current;
    tokenBufferRef.current = "";
    if (!text || !editor || editor.isDestroyed) return;

    const currentRange = normalizeTiptapRange(
      insertRangeRef.current,
      editor.state.doc.content.size,
    );
    insertRangeRef.current = currentRange;

    const transaction = editor.state.tr
      .insertText(text, currentRange.to)
      .setMeta(ALFRED_AI_STREAM_META, true);
    editor.view.dispatch(transaction);
    updatePillPosition();
  }, [editor, updatePillPosition]);

  const queueToken = useCallback(
    (token: string) => {
      tokenBufferRef.current += token;
      // Track the canonical markdown text in parallel so we can re-render
      // the streamed plain text as proper TipTap nodes on MESSAGE_END.
      markdownBufferRef.current += token;
      if (tokenFrameRef.current !== null) return;
      tokenFrameRef.current = window.requestAnimationFrame(() => {
        tokenFrameRef.current = null;
        flushTokenBuffer();
      });
    },
    [flushTokenBuffer],
  );

  /**
   * Replace the streamed plain-text AI region with markdown-rendered nodes.
   *
   * Called on AG-UI MESSAGE_END. The TipTap `Markdown` extension is already
   * registered, so `insertContentAt` with `contentType: "markdown"` parses
   * the buffer into proper nodes (headings, lists, bold, links, etc).
   *
   * Returning early when the buffer has no markdown syntax avoids a useless
   * round-trip through the parser for plain prose generations.
   */
  const renderMarkdownAtRange = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    const markdown = markdownBufferRef.current;
    if (!markdown) return;

    // Cheap check: if the message has no markdown syntax, the streamed plain
    // text is already correct — skip the parse + replace churn.
    const hasMarkdown = /(^|\n)#{1,6} |[*_]{1,2}\S|`[^`]|^- |^\d+\. |^>|\[[^\]]+\]\(/m.test(
      markdown,
    );
    if (!hasMarkdown) return;

    const range = normalizeTiptapRange(insertRangeRef.current, editor.state.doc.content.size);
    if (range.from === range.to) return;

    // insertContentAt replaces the [from, to] range with parsed markdown.
    // We tag the transaction with our stream-meta flag so downstream effects
    // (autosave debouncer, etc.) recognize it as AI-driven.
    const beforeSize = editor.state.doc.content.size;
    editor
      .chain()
      .focus(false, { scrollIntoView: false })
      .insertContentAt(
        { from: range.from, to: range.to },
        markdown,
        { contentType: "markdown" },
      )
      .setMeta(ALFRED_AI_STREAM_META, true)
      .run();

    // Re-anchor the insert range to the rendered region. The new size is
    // computed off doc growth — markdown often expands (a `# Heading` line
    // becomes a heading node) or contracts (consecutive blank lines collapse).
    const afterSize = editor.state.doc.content.size;
    const delta = afterSize - beforeSize;
    insertRangeRef.current = {
      from: range.from,
      to: range.to + delta,
    };
  }, [editor]);

  /* ---- action handlers ------------------------------------------ */

  const handleAccept = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    const currentOriginalRange = originalRangeRef.current;
    if (currentOriginalRange) {
      // Edit mode: delete the original text range. The AI text is already
      // inserted AFTER the original, so deleting the original leaves only
      // the accepted AI text. The insert range is remapped automatically.
      const { from, to } = normalizeTiptapRange(
        currentOriginalRange,
        editor.state.doc.content.size,
      );
      if (from < to) {
        const tr = editor.state.tr.delete(from, to);
        editor.view.dispatch(tr);
      }

      toast.success("AI edit applied");
    } else {
      toast.success("AI text inserted");
    }
    onFinish("accept");
  }, [editor, onFinish]);

  const handleDiscard = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    abortRef.current?.abort();
    discardInserted();
    onFinish("discard");
  }, [editor, discardInserted, onFinish]);

  /**
   * Run a follow-up against the just-streamed output.
   *
   * For `rewrite` and `transform` mode follow-ups we delete the prior AI
   * region first — the new stream replaces it. For `extend` mode (only
   * `continue_writing`) we leave the prior text in place; new tokens will
   * be inserted at the end of the existing range so the result reads as
   * one continuous passage.
   *
   * In all cases we reset the markdown buffer and re-anchor the insert
   * range, then bubble the resolved instruction up to the parent which
   * flips state back to `streaming`.
   */
  const handleFollowup = useCallback(
    (followup: FollowupDef) => {
      if (!editor || editor.isDestroyed) return;

      const ctx = {
        prevOutput: lastOutputRef.current,
        originalSelection: originalRangeRef.current?.text ?? null,
        pageTitle: documentTitle ?? "",
      };

      let instruction: string;
      try {
        instruction = resolveFollowup(followup.id, ctx);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Follow-up failed");
        return;
      }

      const range = normalizeTiptapRange(insertRangeRef.current, editor.state.doc.content.size);

      if (followup.mode === "rewrite" || followup.mode === "transform") {
        // Replace the prior AI text with the new stream — delete first.
        if (range.from < range.to) {
          const tr = editor.state.tr.delete(range.from, range.to).setMeta(ALFRED_AI_STREAM_META, true);
          editor.view.dispatch(tr);
        }
        insertRangeRef.current = { from: range.from, to: range.from };
      }
      // For extend mode the new tokens insert at `range.to` and the prior
      // text remains. insertRangeRef is left as-is so the next stream's
      // tokens append to the existing range.

      tokenBufferRef.current = "";
      markdownBufferRef.current = "";
      isFollowupRef.current = true;
      setActionBarPos(null);
      onFollowup(instruction);
    },
    [editor, documentTitle, onFollowup],
  );

  /* ---- streaming effect ----------------------------------------- */

  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    const docSize = editor.state.doc.content.size;
    insertRangeRef.current = normalizeTiptapRange({ from: insertAt, to: insertAt }, docSize);
    originalRangeRef.current = originalRange
      ? {
          ...normalizeTiptapRange({ from: originalRange.from, to: originalRange.to }, docSize),
          text: originalRange.text,
        }
      : null;
  }, [editor, insertAt, originalRange]);

  useEffect(() => {
    if (!editor || editor.isDestroyed || state.status === "idle") return;

    const handleTransaction = ({ transaction }: { transaction: Transaction }) => {
      if (!transaction.docChanged) return;

      const docSize = transaction.doc.content.size;
      insertRangeRef.current = remapTiptapRange(
        insertRangeRef.current,
        transaction.mapping,
        docSize,
      );

      if (originalRangeRef.current) {
        // Use assoc=-1 for both endpoints so the original range stays put
        // when a transaction inserts content AT either boundary. This is
        // critical when our pre-stream empty-paragraph-insert lands exactly
        // at originalRange.to: with the default assoc=+1 the boundary would
        // shift forward and originalRange would expand to cover the AI
        // output, causing accept to delete both the original AND the AI
        // text. Using -1 keeps originalRange anchored to the original
        // paragraph regardless of inserts past it.
        const { from, to } = originalRangeRef.current;
        const mappedFrom = transaction.mapping.map(from, -1);
        const mappedTo = transaction.mapping.map(to, -1);
        const clamped =
          mappedFrom <= mappedTo
            ? { from: mappedFrom, to: mappedTo }
            : { from: mappedTo, to: mappedFrom };
        originalRangeRef.current = {
          ...originalRangeRef.current,
          from: Math.max(0, Math.min(clamped.from, docSize)),
          to: Math.max(0, Math.min(clamped.to, docSize)),
        };
      }

      if (state.status === "streaming") {
        updatePillPosition();
      } else if (state.status === "done") {
        updateActionBarPosition();
      }
    };

    editor.on("transaction", handleTransaction);
    return () => {
      editor.off("transaction", handleTransaction);
    };
  }, [editor, state.status, updateActionBarPosition, updatePillPosition]);

  useEffect(() => {
    if (state.status !== "streaming") return;

    const ac = new AbortController();
    abortRef.current = ac;

    const docSize = editor.state.doc.content.size;
    if (isFollowupRef.current) {
      // handleFollowup already positioned insertRangeRef correctly for the
      // re-stream (deleted the prior AI region for rewrite/transform mode,
      // or left it in place for extend mode). Just clamp it against the
      // current doc size.
      insertRangeRef.current = normalizeTiptapRange(insertRangeRef.current, docSize);
      isFollowupRef.current = false;
    } else {
      const initialRange = normalizeTiptapRange({ from: insertAt, to: insertAt }, docSize);
      // If the initial insert position lands at a *between-block* position
      // (e.g. after a select-all-then-Cmd+J selection that ends at the
      // closing tag of the last paragraph), raw `tr.insertText` will create
      // a new paragraph for each batched flush — splitting the streamed
      // output across N paragraphs. Land the cursor inside a textblock by
      // dispatching a one-time empty-paragraph insert at the boundary, then
      // anchor the insert range inside it. Inside-textblock positions are
      // safe — `insertText` appends within the existing paragraph.
      try {
        const $pos = editor.state.doc.resolve(initialRange.to);
        if (!$pos.parent.isTextblock) {
          // Between-block case: insert an empty paragraph node here and
          // re-anchor the insert range inside it.
          const paragraph = editor.schema.nodes.paragraph?.create();
          if (paragraph) {
            const tr = editor.state.tr
              .insert(initialRange.to, paragraph)
              .setMeta(ALFRED_AI_STREAM_META, true);
            editor.view.dispatch(tr);
            // The new paragraph spans [initialRange.to, initialRange.to + 2]:
            // open tag at to, content at to+1, close tag at to+1. Position
            // the insert range at to+1 so subsequent insertText appends
            // inside the paragraph.
            const inside = initialRange.to + 1;
            insertRangeRef.current = { from: inside, to: inside };
          } else {
            insertRangeRef.current = initialRange;
          }
        } else {
          insertRangeRef.current = initialRange;
        }
      } catch {
        insertRangeRef.current = initialRange;
      }
    }
    // Fresh stream — clear the markdown buffer so this run's text doesn't
    // get mingled with anything left over from a prior run/follow-up.
    markdownBufferRef.current = "";
    // Close any open follow-up menus from the prior `done` state.
    setMoreMenuOpen(false);
    setActiveSubmenu(null);

    const run = async () => {
      try {
        const isEdit = originalRange !== null;
        const { draftExcerpt, pageText } = buildWritingContext();
        const threadId = `note-inline:${documentId ?? "local"}:${Date.now()}`;

        await streamWritingCompose({
          intent: isEdit ? "edit" : "compose",
          instruction: resolveInstruction(state.instruction),
          selection: originalRange?.text ?? "",
          draft: draftExcerpt,
          pageTitle: documentTitle ?? "",
          pageText,
          preset: "notion",
          threadId,
          signal: ac.signal,
          onMessageStart: () => {
            // New message boundary opened — reset the markdown buffer so the
            // first follow-up's content doesn't append to the prior run.
            markdownBufferRef.current = "";
          },
          onMessageEnd: () => {
            // Drain any pending tokens so the plain text is fully on-screen,
            // then re-render the AI region as parsed markdown nodes.
            flushTokenBuffer();
            // Capture the full streamed text BEFORE the markdown parse so
            // follow-ups can feed it back as `prevOutput`. We use the
            // markdown buffer rather than reading from the doc — the doc
            // representation may have lost mark/structure information.
            lastOutputRef.current = markdownBufferRef.current;
            renderMarkdownAtRange();
          },
          onToken: (token: string) => {
            if (!token || editor.isDestroyed) return;
            try {
              queueToken(token);
            } catch (error) {
              ac.abort();
              const message = error instanceof Error ? error.message : "AI insert failed";
              toast.error(message);
              discardInserted();
              onFinish("discard");
            }
          },
          onComplete: () => {
            flushTokenBuffer();
            // Safety net for the prior-output capture: if MESSAGE_END didn't
            // fire (legacy server, dropped frame), we still want lastOutputRef
            // populated for follow-ups.
            if (!lastOutputRef.current) {
              lastOutputRef.current = markdownBufferRef.current;
            }
            // Idempotent — returns early if the buffer has no markdown syntax
            // OR if the range has already been markdown-rendered (no-op when
            // MESSAGE_END already triggered the render).
            renderMarkdownAtRange();
            updateActionBarPosition();
            onStreamComplete();
          },
          onError: (error: Error) => {
            toast.error(error.message || "AI streaming failed");
            discardInserted();
            onFinish("discard");
          },
        });
      } catch {
        // Errors are handled in onError / abort
      }
    };

    run();

    return () => {
      if (tokenFrameRef.current !== null) {
        window.cancelAnimationFrame(tokenFrameRef.current);
        tokenFrameRef.current = null;
      }
      tokenBufferRef.current = "";
      markdownBufferRef.current = "";
      ac.abort();
      abortRef.current = null;
    };
  }, [
    state,
    insertAt,
    originalRange,
    documentTitle,
    documentId,
    editor,
    onFinish,
    onStreamComplete,
    updateActionBarPosition,
    updatePillPosition,
    flushTokenBuffer,
    queueToken,
    discardInserted,
    buildWritingContext,
    resolveInstruction,
    renderMarkdownAtRange,
  ]);

  /* ---- keyboard shortcuts --------------------------------------- */

  // Map single-letter follow-up shortcuts to their definitions.
  const shortcutMap = useMemo(() => {
    const map = new Map<string, FollowupDef>();
    for (const followup of FOLLOWUPS) {
      if (followup.shortcut) {
        map.set(followup.shortcut.toLowerCase(), followup);
      }
    }
    return map;
  }, []);

  useEffect(() => {
    if (state.status !== "done") return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept when the user is typing in any input/contenteditable.
      const target = e.target as HTMLElement | null;
      const isEditable =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.isContentEditable;

      if (e.key === "Tab" || e.key === "Enter") {
        e.preventDefault();
        handleAccept();
        return;
      }

      if (e.key === "Escape") {
        e.preventDefault();
        if (activeSubmenu) {
          setActiveSubmenu(null);
        } else if (moreMenuOpen) {
          setMoreMenuOpen(false);
        } else {
          handleDiscard();
        }
        return;
      }

      if (isEditable || e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return;

      const followup = shortcutMap.get(e.key.toLowerCase());
      if (followup) {
        e.preventDefault();
        handleFollowup(followup);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [state.status, handleAccept, handleDiscard, handleFollowup, shortcutMap, moreMenuOpen, activeSubmenu]);

  /* ---- action bar position on done ------------------------------ */

  useEffect(() => {
    if (state.status === "done") {
      updateActionBarPosition();
    }
  }, [state.status, updateActionBarPosition]);

  /* ---- render --------------------------------------------------- */

  if (state.status === "idle") return null;

  // "Writing..." pill while streaming
  if (state.status === "streaming") {
    if (!pillPos) return null;
    return (
      <div
        className="border-border bg-card fixed z-50 flex items-center gap-1.5 rounded-md border px-2.5 py-1 shadow-sm"
        style={{ top: pillPos.top, left: pillPos.left }}
      >
        <Sparkles className="text-primary h-3 w-3 animate-pulse" />
        <span className="text-primary font-mono text-[10px] tracking-wider uppercase">
          Writing...
        </span>
      </div>
    );
  }

  // Action bar when done
  if (!actionBarPos) return null;

  const primaries = primaryFollowups();
  const transformFollowups = FOLLOWUPS.filter((f) => f.group === "transform");
  const toneFollowups = FOLLOWUPS.filter((f) => f.group === "tone");
  const translateFollowups = FOLLOWUPS.filter((f) => f.group === "translate");

  const followupChipClass = cn(
    "flex items-center gap-1.5 rounded-md px-2 py-1.5",
    "text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
    "font-mono text-[10px] tracking-wider uppercase",
    "transition-colors",
  );

  const submenuItemClass = cn(
    "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left",
    "text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
    "font-mono text-[10px] tracking-wider uppercase",
    "transition-colors",
  );

  return (
    <div
      className="fixed z-50"
      style={{ top: actionBarPos.top, left: actionBarPos.left }}
    >
      {/* Primary action row — Accept / Discard + top follow-ups */}
      <div className="border-border bg-card flex items-center gap-1 rounded-lg border p-1 shadow-md">
        <button
          type="button"
          onClick={handleAccept}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-2.5 py-1.5",
            "bg-primary text-primary-foreground hover:bg-primary/90",
            "font-mono text-[10px] tracking-wider uppercase",
            "transition-colors",
          )}
          title="Accept (Tab or Enter)"
        >
          <Check className="h-3 w-3" />
          Accept
        </button>

        <button
          type="button"
          onClick={handleDiscard}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-2.5 py-1.5",
            "text-muted-foreground hover:bg-secondary hover:text-foreground",
            "font-mono text-[10px] tracking-wider uppercase",
            "transition-colors",
          )}
          title="Discard (Esc)"
        >
          <X className="h-3 w-3" />
          Discard
        </button>

        <div className="bg-border mx-0.5 h-5 w-px" aria-hidden="true" />

        {primaries.map((followup) => {
          const Icon = followup.icon;
          return (
            <button
              key={followup.id}
              type="button"
              onClick={() => handleFollowup(followup)}
              className={followupChipClass}
              title={
                followup.shortcut
                  ? `${followup.label} (${followup.shortcut.toUpperCase()})`
                  : followup.label
              }
            >
              <Icon className="h-3 w-3" />
              {followup.label}
            </button>
          );
        })}

        <div className="bg-border mx-0.5 h-5 w-px" aria-hidden="true" />

        <button
          type="button"
          onClick={() => {
            setMoreMenuOpen((v) => !v);
            setActiveSubmenu(null);
          }}
          className={cn(
            followupChipClass,
            moreMenuOpen && "bg-[var(--alfred-accent-subtle)] text-foreground",
          )}
          title="More options"
          aria-expanded={moreMenuOpen}
        >
          More
        </button>

        <button
          type="button"
          onClick={() => onEditInstruction(state.instruction)}
          className={followupChipClass}
          title="Tell AI what to change"
        >
          <Pencil className="h-3 w-3" />
          Tell AI…
        </button>
      </div>

      {/* "More" overflow menu — transform, tone, translate */}
      {moreMenuOpen && (
        <div
          className="border-border bg-card absolute left-0 mt-1.5 w-64 rounded-lg border p-1.5 shadow-lg"
          role="menu"
        >
          <div className="mb-1 px-2 pt-1 font-mono text-[9px] tracking-wider text-[var(--alfred-text-tertiary)] uppercase">
            Transform
          </div>
          {transformFollowups.map((followup) => {
            const Icon = followup.icon;
            return (
              <button
                key={followup.id}
                type="button"
                role="menuitem"
                onClick={() => handleFollowup(followup)}
                className={submenuItemClass}
              >
                <Icon className="h-3 w-3 shrink-0" />
                {followup.label}
              </button>
            );
          })}

          <div className="bg-border my-1 h-px" aria-hidden="true" />

          <button
            type="button"
            role="menuitem"
            onClick={() => setActiveSubmenu(activeSubmenu === "tone" ? null : "tone")}
            className={cn(
              submenuItemClass,
              "justify-between",
              activeSubmenu === "tone" && "bg-[var(--alfred-accent-subtle)] text-foreground",
            )}
            aria-expanded={activeSubmenu === "tone"}
          >
            <span className="flex items-center gap-2">
              <Sparkles className="h-3 w-3" />
              Change tone
            </span>
            <span className="text-[8px]">›</span>
          </button>

          <button
            type="button"
            role="menuitem"
            onClick={() => setActiveSubmenu(activeSubmenu === "translate" ? null : "translate")}
            className={cn(
              submenuItemClass,
              "justify-between",
              activeSubmenu === "translate" && "bg-[var(--alfred-accent-subtle)] text-foreground",
            )}
            aria-expanded={activeSubmenu === "translate"}
          >
            <span className="flex items-center gap-2">
              <Sparkles className="h-3 w-3" />
              Translate
            </span>
            <span className="text-[8px]">›</span>
          </button>
        </div>
      )}

      {/* Submenu (tone/translate) — opens to the right of "More" */}
      {moreMenuOpen && activeSubmenu && (
        <div
          className="border-border bg-card absolute mt-1.5 ml-1 w-52 rounded-lg border p-1.5 shadow-lg"
          style={{ left: 16 * 16 }}
          role="menu"
        >
          <div className="mb-1 px-2 pt-1 font-mono text-[9px] tracking-wider text-[var(--alfred-text-tertiary)] uppercase">
            {activeSubmenu === "tone" ? "Tone" : "Translate to"}
          </div>
          {(activeSubmenu === "tone" ? toneFollowups : translateFollowups).map((followup) => {
            const Icon = followup.icon;
            return (
              <button
                key={followup.id}
                type="button"
                role="menuitem"
                onClick={() => handleFollowup(followup)}
                className={submenuItemClass}
              >
                <Icon className="h-3 w-3 shrink-0" />
                {followup.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
