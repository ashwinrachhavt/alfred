"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { type Editor } from "@tiptap/react";
import { toast } from "sonner";
import { Check, Pencil, RotateCcw, Sparkles, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { streamAIInline } from "@/lib/api/ai-stream";
import { completeText } from "@/lib/api/ai-assist";

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
  onFinish,
  onStreamComplete,
  onRetry,
  onEditInstruction,
}: AiStreamingControllerProps) {
  const abortRef = useRef<AbortController | null>(null);
  const insertRangeRef = useRef<{ from: number; to: number }>({
    from: insertAt,
    to: insertAt,
  });

  const [pillPos, setPillPos] = useState<{ top: number; left: number } | null>(
    null,
  );
  const [actionBarPos, setActionBarPos] = useState<{
    top: number;
    left: number;
  } | null>(null);

  /* ---- helpers --------------------------------------------------- */

  const updateActionBarPosition = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    try {
      const to = insertRangeRef.current.to;
      if (to > editor.state.doc.content.size) return;
      const coords = editor.view.coordsAtPos(to);
      setActionBarPos({ top: coords.bottom + 8, left: coords.left });
    } catch {
      // coordsAtPos can throw if the position is out of range
    }
  }, [editor]);

  const updatePillPosition = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    try {
      const to = insertRangeRef.current.to;
      if (to > editor.state.doc.content.size) return;
      const coords = editor.view.coordsAtPos(to);
      setPillPos({ top: coords.bottom + 8, left: coords.left });
    } catch {
      // ignore
    }
  }, [editor]);

  const discardInserted = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    const { from, to } = insertRangeRef.current;
    if (from < to) {
      const tr = editor.state.tr.delete(from, to);
      editor.view.dispatch(tr);
    }
  }, [editor]);

  /* ---- action handlers ------------------------------------------ */

  const handleAccept = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    if (originalRange) {
      // Edit mode: delete the original text range. The AI text is already
      // inserted AFTER the original, so deleting the original shifts
      // the insert range backwards.
      const deleteLen = originalRange.to - originalRange.from;
      const tr = editor.state.tr.delete(originalRange.from, originalRange.to);
      editor.view.dispatch(tr);

      // Adjust insert range ref since deletion before shifts positions
      insertRangeRef.current = {
        from: insertRangeRef.current.from - deleteLen,
        to: insertRangeRef.current.to - deleteLen,
      };

      toast.success("AI edit applied");
    } else {
      toast.success("AI text inserted");
    }
    onFinish("accept");
  }, [editor, originalRange, onFinish]);

  const handleDiscard = useCallback(() => {
    if (!editor || editor.isDestroyed) return;
    abortRef.current?.abort();
    discardInserted();
    onFinish("discard");
  }, [editor, discardInserted, onFinish]);

  /* ---- streaming effect ----------------------------------------- */

  useEffect(() => {
    if (state.status !== "streaming") return;

    const ac = new AbortController();
    abortRef.current = ac;

    let currentPos = insertAt;
    insertRangeRef.current = { from: insertAt, to: insertAt };

    const run = async () => {
      try {
        if (state.instruction === "__CONTINUE__") {
          // Special case: use completeText instead of streaming
          const docText = editor.state.doc.textBetween(
            0,
            Math.min(insertAt, editor.state.doc.content.size),
            "\n",
          );
          const contextBefore = docText.slice(-1000);

          const result = await completeText(contextBefore, "", "");
          if (ac.signal.aborted) return;

          const tr = editor.state.tr.insertText(result, currentPos);
          editor.view.dispatch(tr);
          currentPos += result.length;
          insertRangeRef.current = {
            from: insertAt,
            to: currentPos,
          };
          updateActionBarPosition();
          onStreamComplete();
        } else {
          // Normal streaming case
          const isEdit = originalRange !== null;
          const intentArgs = isEdit
            ? { text: originalRange.text, instruction: state.instruction }
            : {
                text: editor.state.doc
                  .textBetween(
                    Math.max(0, insertAt - 1000),
                    Math.min(insertAt, editor.state.doc.content.size),
                    "\n",
                  )
                  .slice(-1000),
                instruction: "Generate new content: " + state.instruction,
              };

          await streamAIInline({
            intent: "edit_text",
            intentArgs,
            onToken: (token: string) => {
              const tr = editor.state.tr.insertText(token, currentPos);
              editor.view.dispatch(tr);
              currentPos += token.length;
              insertRangeRef.current = {
                from: insertAt,
                to: currentPos,
              };
              updatePillPosition();
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
            signal: ac.signal,
          });
        }
      } catch {
        // Errors are handled in onError / abort
      }
    };

    run();

    return () => {
      ac.abort();
      abortRef.current = null;
    };
  }, [state, insertAt, originalRange, editor, onFinish, onStreamComplete, updateActionBarPosition, updatePillPosition, discardInserted]);

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
        className="fixed z-50 flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1 shadow-sm"
        style={{ top: pillPos.top, left: pillPos.left }}
      >
        <Sparkles className="h-3 w-3 animate-pulse text-primary" />
        <span className="font-mono text-[10px] uppercase tracking-wider text-primary">
          Writing...
        </span>
      </div>
    );
  }

  // Action bar when done
  if (!actionBarPos) return null;

  return (
    <div
      className="fixed z-50 flex items-center gap-1 rounded-lg border border-border bg-card p-1 shadow-md"
      style={{ top: actionBarPos.top, left: actionBarPos.left }}
    >
      {/* Accept */}
      <button
        type="button"
        onClick={handleAccept}
        className={cn(
          "flex items-center gap-1.5 rounded-md px-2.5 py-1.5",
          "bg-primary text-primary-foreground",
          "font-mono text-[10px] uppercase tracking-wider",
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
        onClick={onRetry}
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
