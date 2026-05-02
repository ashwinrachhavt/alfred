"use client";

/**
 * DecompositionReviewUI (T10)
 *
 * Full-screen overlay that streams candidate cards from the backend via SSE,
 * lets the user edit / accept / reject each, then commits the accepted ones
 * through the bulk-from-decomposition route.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";
import { BLOOM_LABELS, type BloomLevel } from "@/lib/bloom";
import { useBulkFromDecomposition } from "@/features/workspace/mutations";
import {
  useZettelWorkspaceStore,
} from "@/lib/stores/zettel-workspace-store";
import {
  streamDecomposeEvents,
  type SSEEvent,
} from "@/components/zettels/workspace/stream-client";
import { useWorkspaceContext } from "@/components/zettels/workspace/workspace-context";

type Candidate = {
  title: string;
  content: string;
  bloom_level: BloomLevel;
  tags: string[];
  accepted: boolean;
};

function coerceBloom(level: unknown): BloomLevel {
  const n = Number(level);
  if (n >= 1 && n <= 6) return n as BloomLevel;
  return 2;
}

function readCandidateFromEvent(evt: SSEEvent): Candidate | null {
  // The server emits {payload: {title, content, bloom_level, tags?}} nested.
  const payload =
    (evt.data.payload as Record<string, unknown> | undefined) ?? evt.data;
  if (!payload || typeof payload !== "object") return null;
  const title = String((payload as Record<string, unknown>).title ?? "").trim();
  const content = String((payload as Record<string, unknown>).content ?? "");
  if (!title && !content) return null;
  const tagsRaw = (payload as Record<string, unknown>).tags;
  const tags = Array.isArray(tagsRaw)
    ? tagsRaw.filter((t): t is string => typeof t === "string")
    : [];
  return {
    title: title || "Untitled",
    content,
    bloom_level: coerceBloom((payload as Record<string, unknown>).bloom_level),
    tags,
    accepted: true,
  };
}

export function DecompositionReviewUI() {
  const { decomposition, closeDecomposition } = useWorkspaceContext();
  const sessionId = useZettelWorkspaceStore((s) => s.sessionId);
  const registerAbortController = useZettelWorkspaceStore(
    (s) => s.registerAbortController,
  );
  const abortKey = useZettelWorkspaceStore((s) => s.abortKey);

  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [streamDone, setStreamDone] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const bulk = useBulkFromDecomposition();
  const abortKeyRef = useRef<string | null>(null);

  // Kick off the stream on mount / when the raw text changes.
  useEffect(() => {
    if (!decomposition) return;
    setCandidates([]);
    setStreamDone(false);
    setStreamError(null);

    const controller = new AbortController();
    const key = `decompose:session-${sessionId ?? "anon"}`;
    abortKeyRef.current = key;
    registerAbortController(key, controller);

    let cancelled = false;

    (async () => {
      try {
        const gen = streamDecomposeEvents(
          {
            raw_text: decomposition.rawText,
            session_id: sessionId ?? undefined,
          },
          controller.signal,
        );
        for await (const evt of gen) {
          if (cancelled) break;
          if (evt.event === "candidate_ready") {
            const c = readCandidateFromEvent(evt);
            if (c) setCandidates((prev) => [...prev, c]);
          } else if (evt.event === "decompose_complete") {
            setStreamDone(true);
          } else if (evt.event === "error") {
            setStreamError(String(evt.data.message ?? "Stream error"));
          }
        }
        if (!cancelled) setStreamDone(true);
      } catch (err) {
        if ((err as Error)?.name === "AbortError") return;
        if (!cancelled) {
          setStreamError(
            err instanceof Error ? err.message : "Decompose failed",
          );
        }
      }
    })();

    return () => {
      cancelled = true;
      if (abortKeyRef.current) abortKey(abortKeyRef.current);
      abortKeyRef.current = null;
    };
    // We intentionally only depend on decomposition/sessionId — the store actions are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [decomposition, sessionId]);

  const handleClose = useCallback(() => {
    if (abortKeyRef.current) {
      abortKey(abortKeyRef.current);
      abortKeyRef.current = null;
    }
    closeDecomposition();
  }, [abortKey, closeDecomposition]);

  const updateCandidate = (idx: number, patch: Partial<Candidate>) =>
    setCandidates((prev) =>
      prev.map((c, i) => (i === idx ? { ...c, ...patch } : c)),
    );

  const acceptedCount = useMemo(
    () => candidates.filter((c) => c.accepted).length,
    [candidates],
  );

  const handleCommit = async () => {
    const accepted = candidates.filter((c) => c.accepted);
    if (accepted.length === 0) {
      toast.message("Nothing to commit", {
        description: "Accept at least one candidate.",
      });
      return;
    }
    try {
      const result = await bulk.mutateAsync({
        session_id: sessionId ?? null,
        candidates: accepted.map((c) => ({
          title: c.title,
          content: c.content,
          bloom_level: c.bloom_level,
          tags: c.tags.length > 0 ? c.tags : undefined,
        })),
      });
      toast.success("Decomposition committed", {
        description: `Created ${result.created_card_ids.length} cards · ${result.link_count} links`,
      });
      handleClose();
    } catch (err) {
      toast.error("Could not commit", {
        description: err instanceof Error ? err.message : String(err),
      });
    }
  };

  if (!decomposition) return null;

  return (
    <div
      className="fixed inset-0 z-40 bg-background/95 backdrop-blur"
      role="dialog"
      aria-modal="true"
      aria-label="Decomposition review"
    >
      <div className="mx-auto flex h-full max-w-4xl flex-col gap-6 px-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-serif text-[28px] leading-[1.2] text-foreground">
              Review split
            </h2>
            <div className="mt-1 font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
              {streamDone ? "COMPLETE" : "STREAMING"} · {candidates.length}{" "}
              {candidates.length === 1 ? "CANDIDATE" : "CANDIDATES"}
              {streamError ? ` · ERROR: ${streamError}` : ""}
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="rounded border border-[var(--alfred-ruled-line)] p-1.5 text-foreground transition-colors hover:bg-accent"
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Candidates scroll list */}
        <div className="flex-1 overflow-y-auto pr-1">
          {candidates.length === 0 && !streamError && (
            <div className="flex items-center justify-center py-16 font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
              Listening for candidates...
            </div>
          )}
          <ul className="flex flex-col gap-4">
            {candidates.map((c, idx) => (
              <li
                key={idx}
                className={cn(
                  "rounded-lg border border-[var(--alfred-ruled-line)] bg-background p-6 transition-opacity",
                  !c.accepted && "opacity-50",
                )}
              >
                <div className="flex items-start justify-between gap-4">
                  <input
                    value={c.title}
                    onChange={(e) =>
                      updateCandidate(idx, { title: e.target.value })
                    }
                    className="min-w-0 flex-1 border-none bg-transparent font-serif text-[20px] text-foreground placeholder:text-muted-foreground focus:outline-none"
                    placeholder="Untitled"
                    aria-label={`Candidate ${idx + 1} title`}
                  />
                  <label className="flex shrink-0 items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
                    <input
                      type="checkbox"
                      checked={c.accepted}
                      onChange={(e) =>
                        updateCandidate(idx, { accepted: e.target.checked })
                      }
                    />
                    Accept
                  </label>
                </div>

                <textarea
                  value={c.content}
                  onChange={(e) =>
                    updateCandidate(idx, { content: e.target.value })
                  }
                  className="mt-3 min-h-24 w-full resize-y rounded border border-transparent bg-transparent p-0 font-serif text-[15px] leading-[1.55] text-foreground focus:border-[var(--alfred-ruled-line)] focus:outline-none"
                  aria-label={`Candidate ${idx + 1} body`}
                />

                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <label className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
                    Bloom
                    <select
                      value={c.bloom_level}
                      onChange={(e) =>
                        updateCandidate(idx, {
                          bloom_level: coerceBloom(e.target.value),
                        })
                      }
                      className="rounded border border-[var(--alfred-ruled-line)] bg-transparent px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-foreground"
                    >
                      {([1, 2, 3, 4, 5, 6] as BloomLevel[]).map((lvl) => (
                        <option key={lvl} value={lvl}>
                          {lvl} · {BLOOM_LABELS[lvl]}
                        </option>
                      ))}
                    </select>
                  </label>

                  <input
                    value={c.tags.join(", ")}
                    onChange={(e) => {
                      const raw = e.target.value;
                      const tags = raw
                        .split(",")
                        .map((t) => t.trim())
                        .filter(Boolean);
                      updateCandidate(idx, { tags });
                    }}
                    className="flex-1 rounded border border-[var(--alfred-ruled-line)] bg-transparent px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-foreground placeholder:text-[var(--alfred-text-tertiary)] focus:outline-none"
                    placeholder="Tags (comma separated)"
                    aria-label={`Candidate ${idx + 1} tags`}
                  />
                </div>
              </li>
            ))}
          </ul>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-[var(--alfred-ruled-line)] pt-4">
          <button
            type="button"
            onClick={handleClose}
            className="rounded border border-[var(--alfred-ruled-line)] px-3 py-1.5 font-mono text-[10px] font-medium uppercase tracking-wider text-foreground transition-colors hover:bg-accent"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleCommit}
            disabled={bulk.isPending || acceptedCount === 0}
            className={cn(
              "rounded bg-primary px-3 py-1.5 font-mono text-[10px] font-medium uppercase tracking-wider text-primary-foreground transition-colors hover:opacity-90",
              "disabled:cursor-not-allowed disabled:opacity-50",
            )}
          >
            {bulk.isPending
              ? "Committing..."
              : `Commit ${acceptedCount} ${acceptedCount === 1 ? "candidate" : "candidates"}`}
          </button>
        </div>
      </div>
    </div>
  );
}

export default DecompositionReviewUI;
