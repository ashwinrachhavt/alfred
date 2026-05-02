"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";
import {
  useZettelWorkspaceStore,
  type SavedCardState,
} from "@/lib/stores/zettel-workspace-store";
import {
  BLOOM_BG_CLASSES,
  BLOOM_COLOR_CLASSES,
  BLOOM_LABELS,
  type BloomLevel,
} from "@/lib/bloom";
import {
  streamCreationEvents,
  type SSEEvent,
} from "@/components/zettels/workspace/stream-client";
import { GhostSuggestionEditorExt } from "@/components/zettels/workspace/ghost-suggestion-editor-ext";
import { subscribeEditorInsert } from "@/components/zettels/workspace/editor-bus";
import { useWorkspaceContext } from "@/components/zettels/workspace/workspace-context";

type Props = {
  className?: string;
};

const PAUSE_MS = 800;

// Rough approximation: count whitespace-separated tokens.
function countWords(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) return 0;
  return trimmed.split(/\s+/).length;
}

// Rough approximation: [[Title]] occurrences.
function countLinks(text: string): number {
  const matches = text.match(/\[\[[^\]]+\]\]/g);
  return matches ? matches.length : 0;
}

export function WritingSurface({ className }: Props) {
  const sessionId = useZettelWorkspaceStore((s) => s.sessionId);
  const activeDraft = useZettelWorkspaceStore((s) => s.activeDraft);
  const savedCards = useZettelWorkspaceStore((s) => s.savedCards);
  const stackOrder = useZettelWorkspaceStore((s) => s.stackOrder);
  const focusedEntry = useZettelWorkspaceStore((s) => s.focusedEntry);
  const focusEntry = useZettelWorkspaceStore((s) => s.focusEntry);
  const sharedContext = useZettelWorkspaceStore((s) => s.sharedContext);

  const updateDraftContent = useZettelWorkspaceStore(
    (s) => s.updateDraftContent,
  );
  const updateDraftTitle = useZettelWorkspaceStore((s) => s.updateDraftTitle);
  const promoteDraftToSaved = useZettelWorkspaceStore(
    (s) => s.promoteDraftToSaved,
  );
  const registerAbortController = useZettelWorkspaceStore(
    (s) => s.registerAbortController,
  );
  const abortKey = useZettelWorkspaceStore((s) => s.abortKey);
  const persistActiveDraft = useZettelWorkspaceStore(
    (s) => s.persistActiveDraft,
  );
  const startDraft = useZettelWorkspaceStore((s) => s.startDraft);
  const setSavedCardAnalysis = useZettelWorkspaceStore(
    (s) => s.setSavedCardAnalysis,
  );

  const { openDecomposition } = useWorkspaceContext();

  // Determine what we are currently rendering.
  // - focused draft: use activeDraft (live editing)
  // - focused saved card: show it read-only-ish (editing saved cards
  //   is a later milestone; this is still wired for the Ambient panel).
  const focusedSaved: SavedCardState | null = useMemo(() => {
    if (!focusedEntry || focusedEntry.type !== "saved") return null;
    return savedCards.get(focusedEntry.id) ?? null;
  }, [focusedEntry, savedCards]);

  const isEditingDraft = focusedEntry?.type === "draft" && !!activeDraft;

  const content = isEditingDraft
    ? (activeDraft?.content ?? "")
    : (focusedSaved?.content ?? "");
  const title = isEditingDraft
    ? (activeDraft?.title ?? "")
    : (focusedSaved?.title ?? "");

  const bloomLevel: BloomLevel = (isEditingDraft
    ? (activeDraft?.bloom?.inferredLevel ?? 1)
    : (focusedSaved?.bloom.inferredLevel ?? 1)) as BloomLevel;

  const wordCount = useMemo(() => countWords(content), [content]);
  const linkCount = useMemo(() => countLinks(content), [content]);

  // --- Streaming creation on typing pause -----------------------------
  const pauseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const kickCreationStream = useCallback(async () => {
    if (!activeDraft) return;
    if (activeDraft.content.trim().length < 20) return; // skip noise

    const clientId = activeDraft.clientId;
    const abortKeyForDraft = `draft:${clientId}`;
    const controller = new AbortController();
    registerAbortController(abortKeyForDraft, controller);

    const derivedTitle =
      activeDraft.title.trim() ||
      activeDraft.content.trim().split("\n")[0]?.slice(0, 80) ||
      "Untitled card";

    try {
      const gen = streamCreationEvents(
        {
          title: derivedTitle,
          content: activeDraft.content,
          session_id: sessionId ?? undefined,
          topic: sharedContext.topic,
          tags: sharedContext.tags,
        },
        controller.signal,
      );

      let finalCardId: number | null = null;
      let finalTitle = derivedTitle;

      const connections: Array<{
        card_id: number;
        title: string;
        score: number;
        reason: string;
      }> = [];

      for await (const evt of gen as AsyncGenerator<SSEEvent>) {
        if (evt.event === "card_saved") {
          finalCardId = Number(evt.data.id ?? 0);
          finalTitle = String(evt.data.title ?? derivedTitle);
        } else if (evt.event === "links_found") {
          const suggestions = (evt.data.suggestions as unknown[]) || [];
          connections.length = 0;
          for (const s of suggestions) {
            if (s && typeof s === "object") {
              const obj = s as Record<string, unknown>;
              connections.push({
                card_id: Number(obj.card_id ?? 0),
                title: String(obj.title ?? ""),
                score: Number(obj.score ?? 0),
                reason: String(obj.reason ?? ""),
              });
            }
          }
        } else if (evt.event === "error") {
          // non-fatal: surfaced via the Ambient panel as needed.
        }
      }

      if (finalCardId && finalCardId > 0) {
        const nowIso = new Date().toISOString();
        const saved: SavedCardState = {
          id: finalCardId,
          phase: "ready",
          content: activeDraft.content,
          title: finalTitle,
          bloom: activeDraft.bloom ?? {
            inferredLevel: 1,
            source: "ai_inferred",
          },
          analysis: {
            generatedAtWordCount: wordCount,
            connections,
            enrichment: null,
            decomposition: null,
            bloomQuestions: [],
          },
          enrichmentLastError: null,
          archivedAt: null,
          lastSavedAt: Date.parse(nowIso),
        };
        promoteDraftToSaved(clientId, saved);
        setSavedCardAnalysis(finalCardId, saved.analysis);
      }
    } catch (err) {
      if ((err as Error)?.name === "AbortError") return;
      // Surface only when meaningful — a transient failure while the user
      // is still typing shouldn't interrupt their flow.
      // eslint-disable-next-line no-console
      console.warn("creation stream failed", err);
    }
  }, [
    activeDraft,
    sessionId,
    sharedContext.topic,
    sharedContext.tags,
    registerAbortController,
    promoteDraftToSaved,
    setSavedCardAnalysis,
    wordCount,
  ]);

  // Schedule a pause-save every time the draft content changes.
  useEffect(() => {
    if (!isEditingDraft || !activeDraft) return;
    if (pauseTimer.current) clearTimeout(pauseTimer.current);
    pauseTimer.current = setTimeout(async () => {
      await persistActiveDraft();
      await kickCreationStream();
    }, PAUSE_MS);
    return () => {
      if (pauseTimer.current) clearTimeout(pauseTimer.current);
    };
  }, [
    isEditingDraft,
    activeDraft,
    activeDraft?.content,
    persistActiveDraft,
    kickCreationStream,
  ]);

  // Cancel any in-flight stream on unmount.
  useEffect(() => {
    return () => {
      if (activeDraft) abortKey(`draft:${activeDraft.clientId}`);
    };
  }, [activeDraft, abortKey]);

  // --- Editor-bus: accept external inserts (Ambient "Answer inline") ---
  useEffect(() => {
    return subscribeEditorInsert((text) => {
      if (!isEditingDraft || !activeDraft) {
        // If no active draft, start one and then insert.
        startDraft();
        // Defer so the new draft mounts before we call update.
        setTimeout(() => updateDraftContent(text), 0);
        return;
      }
      const next = activeDraft.content
        ? `${activeDraft.content}\n\n${text}`
        : text;
      updateDraftContent(next);
    });
  }, [isEditingDraft, activeDraft, startDraft, updateDraftContent]);

  // --- Keyboard navigation (Cmd+] / Cmd+[) ----------------------------
  const handleKeyCommand = useCallback(
    (cmd: "submit" | "next" | "prev") => {
      if (cmd === "submit") {
        // Cmd+Enter finalizes: kick any pending save immediately.
        if (pauseTimer.current) clearTimeout(pauseTimer.current);
        void (async () => {
          await persistActiveDraft();
          await kickCreationStream();
          // Once promoted, start a new draft for the next idea.
          startDraft();
        })();
        return;
      }
      if (stackOrder.length === 0) return;
      if (!focusedEntry) {
        focusEntry(stackOrder[0] ?? null);
        return;
      }
      const idx = stackOrder.findIndex((e) => {
        if (e.type !== focusedEntry.type) return false;
        if (e.type === "saved" && focusedEntry.type === "saved") {
          return e.id === focusedEntry.id;
        }
        if (e.type === "draft" && focusedEntry.type === "draft") {
          return e.clientId === focusedEntry.clientId;
        }
        return false;
      });
      if (idx < 0) return;
      const nextIdx = cmd === "next"
        ? Math.min(stackOrder.length - 1, idx + 1)
        : Math.max(0, idx - 1);
      focusEntry(stackOrder[nextIdx] ?? null);
    },
    [
      stackOrder,
      focusedEntry,
      focusEntry,
      persistActiveDraft,
      kickCreationStream,
      startDraft,
    ],
  );

  // --- Decomposition paste heuristic ---
  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLDivElement>) => {
      const text = e.clipboardData.getData("text/plain");
      if (text && text.length > 500) {
        // Ask the user; for T10 we auto-open the decomposition UI.
        openDecomposition({ rawText: text });
        e.preventDefault();
        toast.message("Looks like multiple ideas", {
          description: "Opened decomposition review.",
        });
      }
    },
    [openDecomposition],
  );

  const phaseLabel =
    isEditingDraft && activeDraft
      ? activeDraft.content.trim().length < 10
        ? "DRAFT"
        : "SAVED"
      : focusedSaved
        ? focusedSaved.phase.toUpperCase()
        : "IDLE";

  return (
    <div
      className={cn("flex flex-col gap-6", className)}
      onPasteCapture={handlePaste}
    >
      {/* Title */}
      {isEditingDraft ? (
        <input
          value={title}
          onChange={(e) => updateDraftTitle(e.target.value)}
          placeholder="Untitled card"
          className="w-full border-none bg-transparent font-serif text-[42px] leading-[1.15] text-foreground placeholder:text-muted-foreground focus:outline-none"
          aria-label="Card title"
        />
      ) : (
        <h1 className="font-serif text-[42px] leading-[1.15] text-foreground">
          {title || "Untitled card"}
        </h1>
      )}

      {/* Body */}
      <div className="min-h-[240px]">
        {isEditingDraft ? (
          <GhostSuggestionEditorExt
            value={content}
            placeholder="Start writing. The workspace saves automatically as you pause."
            autoFocus
            onChange={(next) => updateDraftContent(next)}
            onKeyCommand={handleKeyCommand}
          />
        ) : (
          <div className="whitespace-pre-wrap font-serif text-[17px] leading-[1.6] text-foreground">
            {content || (
              <span className="text-muted-foreground">
                This card has no content yet.
              </span>
            )}
          </div>
        )}
      </div>

      {/* Ruled divider + Bloom ladder + chips */}
      <div className="border-t border-[var(--alfred-ruled-line)] pt-4 flex items-center gap-6">
        <div className="flex items-center gap-2" aria-label="Bloom level">
          {([1, 2, 3, 4, 5, 6] as BloomLevel[]).map((lvl) => (
            <span
              key={lvl}
              className={cn(
                "size-2 rounded-full border",
                lvl <= bloomLevel
                  ? cn(BLOOM_BG_CLASSES[bloomLevel], "border-transparent")
                  : "border-[var(--alfred-ruled-line)] bg-transparent",
              )}
              aria-hidden="true"
            />
          ))}
          <span
            className={cn(
              "ml-1 font-mono text-[10px] uppercase tracking-wider",
              BLOOM_COLOR_CLASSES[bloomLevel],
            )}
          >
            {BLOOM_LABELS[bloomLevel]}
          </span>
        </div>

        {sharedContext.topic && (
          <span className="rounded bg-[var(--alfred-accent-muted)] px-2 py-0.5 font-sans text-[10px] uppercase tracking-wide text-primary">
            {sharedContext.topic}
          </span>
        )}
        {sharedContext.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {sharedContext.tags.map((tag) => (
              <span
                key={tag}
                className="rounded border border-[var(--alfred-ruled-line)] px-2 py-0.5 font-sans text-[10px] uppercase tracking-wide text-muted-foreground"
              >
                #{tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Status line */}
      <div className="flex justify-end font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
        {phaseLabel} - {wordCount}W - {linkCount}{" "}
        {linkCount === 1 ? "LINK" : "LINKS"}
      </div>
    </div>
  );
}
