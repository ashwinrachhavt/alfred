"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Transaction } from "@tiptap/pm/state";
import { type Editor } from "@tiptap/react";
import { toast } from "sonner";
import { Check, Pencil, RotateCcw, Sparkles, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { streamWritingCompose } from "@/lib/api/writing-stream";
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
  onRetry: () => void;
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
  onRetry,
  onEditInstruction,
}: AiStreamingControllerProps) {
  const abortRef = useRef<AbortController | null>(null);
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
    const { from, to } = normalizeTiptapRange(insertRangeRef.current, editor.state.doc.content.size);
    if (from < to) {
      const tr = editor.state.tr.delete(from, to);
      editor.view.dispatch(tr);
    }
    insertRangeRef.current = { from, to: from };
    setPillPos(null);
    setActionBarPos(null);
  }, [editor]);

  /* ---- action handlers ------------------------------------------ */

  const handleAccept = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    const currentOriginalRange = originalRangeRef.current;
    if (currentOriginalRange) {
      // Edit mode: delete the original text range. The AI text is already
      // inserted AFTER the original, so deleting the original leaves only
      // the accepted AI text. The insert range is remapped automatically.
      const { from, to } = normalizeTiptapRange(currentOriginalRange, editor.state.doc.content.size);
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

  const handleRetry = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    discardInserted();
    onRetry();
  }, [editor, discardInserted, onRetry]);

  /* ---- streaming effect ----------------------------------------- */

  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    const docSize = editor.state.doc.content.size;
    insertRangeRef.current = normalizeTiptapRange({ from: insertAt, to: insertAt }, docSize);
    originalRangeRef.current = originalRange
      ? {
          ...normalizeTiptapRange(
            { from: originalRange.from, to: originalRange.to },
            docSize,
          ),
          text: originalRange.text,
        }
      : null;
  }, [editor, insertAt, originalRange]);

  useEffect(() => {
    if (!editor || editor.isDestroyed || state.status === "idle") return;

    const handleTransaction = ({ transaction }: { transaction: Transaction }) => {
      if (!transaction.docChanged) return;

      const docSize = transaction.doc.content.size;
      insertRangeRef.current = remapTiptapRange(insertRangeRef.current, transaction.mapping, docSize);

      if (originalRangeRef.current) {
        const mappedOriginalRange = remapTiptapRange(
          originalRangeRef.current,
          transaction.mapping,
          docSize,
        );
        originalRangeRef.current = {
          ...originalRangeRef.current,
          ...mappedOriginalRange,
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
    insertRangeRef.current = normalizeTiptapRange({ from: insertAt, to: insertAt }, docSize);

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
          onToken: (token: string) => {
            if (!token || editor.isDestroyed) return;
            const currentRange = normalizeTiptapRange(
              insertRangeRef.current,
              editor.state.doc.content.size,
            );
            insertRangeRef.current = currentRange;

            try {
              const tr = editor.state.tr.insertText(token, currentRange.to);
              editor.view.dispatch(tr);
              updatePillPosition();
            } catch (error) {
              ac.abort();
              const message = error instanceof Error ? error.message : "AI insert failed";
              toast.error(message);
              discardInserted();
              onFinish("discard");
            }
          },
          onComplete: () => {
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
    discardInserted,
    buildWritingContext,
    resolveInstruction,
  ]);

  /* ---- keyboard shortcuts --------------------------------------- */

  useEffect(() => {
    if (state.status !== "done") return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Tab" || e.key === "Enter") {
        e.preventDefault();
        handleAccept();
      } else if (e.key === "Escape") {
        e.preventDefault();
        handleDiscard();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [state.status, handleAccept, handleDiscard]);

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

  return (
    <div
      className="border-border bg-card fixed z-50 flex items-center gap-1 rounded-lg border p-1 shadow-md"
      style={{ top: actionBarPos.top, left: actionBarPos.left }}
    >
      {/* Accept */}
      <button
        type="button"
        onClick={handleAccept}
        className={cn(
          "flex items-center gap-1.5 rounded-md px-2.5 py-1.5",
          "bg-primary text-primary-foreground",
          "font-mono text-[10px] tracking-wider uppercase",
        )}
      >
        <Check className="h-3 w-3" />
        Accept
      </button>

      {/* Discard */}
      <button
        type="button"
        onClick={handleDiscard}
        className={cn(
          "flex items-center gap-1.5 rounded-md px-2.5 py-1.5",
          "text-muted-foreground hover:bg-secondary hover:text-foreground",
        )}
      >
        <X className="h-3 w-3" />
        Discard
      </button>

      {/* Retry */}
      <button
        type="button"
        onClick={handleRetry}
        className={cn(
          "flex items-center gap-1.5 rounded-md px-2.5 py-1.5",
          "text-muted-foreground hover:bg-secondary hover:text-foreground",
        )}
      >
        <RotateCcw className="h-3 w-3" />
        Retry
      </button>

      {/* Edit instruction */}
      <button
        type="button"
        onClick={() => onEditInstruction(state.instruction)}
        className={cn(
          "flex items-center gap-1.5 rounded-md px-2.5 py-1.5",
          "text-muted-foreground hover:bg-secondary hover:text-foreground",
        )}
      >
        <Pencil className="h-3 w-3" />
        Edit
      </button>
    </div>
  );
}
