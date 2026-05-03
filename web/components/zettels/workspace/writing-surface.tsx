"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Sparkles } from "lucide-react";

import { apiRoutes } from "@/lib/api/routes";
import { apiPostJson } from "@/lib/api/client";

import { cn } from "@/lib/utils";
import { useZettelWorkspaceStore, type SavedCardState } from "@/lib/stores/zettel-workspace-store";
import { BLOOM_BG_CLASSES, BLOOM_COLOR_CLASSES, BLOOM_LABELS, type BloomLevel } from "@/lib/bloom";
import { streamCreationEvents, type SSEEvent } from "@/components/zettels/workspace/stream-client";
import { GhostSuggestionEditorExt } from "@/components/zettels/workspace/ghost-suggestion-editor-ext";
import { subscribeEditorInsert } from "@/components/zettels/workspace/editor-bus";
import { useWorkspaceContext } from "@/components/zettels/workspace/workspace-context";
import {
  ZettelCreationStreamPanel,
  type ZettelCreationStreamPanelState,
} from "@/components/zettels/workspace/zettel-creation-stream-panel";

type Props = {
  className?: string;
};

const PAUSE_MS = 800;
const MIN_STREAM_CHARS = 10;

type StreamPhase = "idle" | "pending" | "streaming" | "saved" | "error";

type DraftStreamKeyInput = {
  clientId: string;
  title: string;
  content: string;
};

function createInitialStreamPanelState(): ZettelCreationStreamPanelState {
  return {
    phase: "idle",
    title: null,
    cardId: null,
    thinking: "",
    links: [],
    enrichment: null,
    bloom: null,
    errors: [],
    steps: {
      saved: false,
      embedded: false,
      searched: false,
      enriched: false,
      completed: false,
    },
  };
}

function readStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function getDraftStreamKey(draft: DraftStreamKeyInput): string {
  return `${draft.clientId}:${draft.title.trim()}:${draft.content.trim()}`;
}

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

  const updateDraftContent = useZettelWorkspaceStore((s) => s.updateDraftContent);
  const updateDraftTitle = useZettelWorkspaceStore((s) => s.updateDraftTitle);
  const promoteDraftToSaved = useZettelWorkspaceStore((s) => s.promoteDraftToSaved);
  const registerAbortController = useZettelWorkspaceStore((s) => s.registerAbortController);
  const abortKey = useZettelWorkspaceStore((s) => s.abortKey);
  const persistActiveDraft = useZettelWorkspaceStore((s) => s.persistActiveDraft);
  const startDraft = useZettelWorkspaceStore((s) => s.startDraft);
  const setSavedCardAnalysis = useZettelWorkspaceStore((s) => s.setSavedCardAnalysis);

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

  const content = isEditingDraft ? (activeDraft?.content ?? "") : (focusedSaved?.content ?? "");
  const title = isEditingDraft ? (activeDraft?.title ?? "") : (focusedSaved?.title ?? "");

  const bloomLevel: BloomLevel = (
    isEditingDraft
      ? (activeDraft?.bloom?.inferredLevel ?? 1)
      : (focusedSaved?.bloom.inferredLevel ?? 1)
  ) as BloomLevel;

  const wordCount = useMemo(() => countWords(content), [content]);
  const linkCount = useMemo(() => countLinks(content), [content]);

  // --- Streaming creation on typing pause -----------------------------
  const pauseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [streamPhase, setStreamPhase] = useState<StreamPhase>("idle");
  const [streamError, setStreamError] = useState<string | null>(null);
  const [savedCardId, setSavedCardId] = useState<number | null>(null);
  const [streamPanelState, setStreamPanelState] = useState<ZettelCreationStreamPanelState>(() =>
    createInitialStreamPanelState(),
  );
  const streamInFlightRef = useRef(false);
  const lastStartedStreamKeyRef = useRef<string | null>(null);

  const kickCreationStream = useCallback(async () => {
    if (!activeDraft) return;
    if (activeDraft.content.trim().length < MIN_STREAM_CHARS) return; // skip noise

    const streamKey = getDraftStreamKey(activeDraft);
    if (streamInFlightRef.current || lastStartedStreamKeyRef.current === streamKey) {
      return;
    }

    streamInFlightRef.current = true;
    lastStartedStreamKeyRef.current = streamKey;

    const clientId = activeDraft.clientId;
    const abortKeyForDraft = `draft:${clientId}`;
    const controller = new AbortController();
    registerAbortController(abortKeyForDraft, controller);

    const derivedTitle =
      activeDraft.title.trim() ||
      activeDraft.content.trim().split("\n")[0]?.slice(0, 80) ||
      "Untitled card";

    setStreamPhase("streaming");
    setStreamError(null);
    setStreamPanelState({
      ...createInitialStreamPanelState(),
      phase: "streaming",
      title: derivedTitle,
    });

    try {
      await persistActiveDraft();

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
          setStreamPanelState((prev) => ({
            ...prev,
            cardId: finalCardId && finalCardId > 0 ? finalCardId : null,
            title: finalTitle,
            steps: { ...prev.steps, saved: true },
          }));
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
          setStreamPanelState((prev) => ({
            ...prev,
            links: connections,
            steps: { ...prev.steps, searched: true },
          }));
        } else if (evt.event === "thinking") {
          const content = String(evt.data.content ?? "");
          if (content) {
            setStreamPanelState((prev) => ({
              ...prev,
              thinking: prev.thinking + content,
            }));
          }
        } else if (evt.event === "embedding_done") {
          setStreamPanelState((prev) => ({
            ...prev,
            steps: { ...prev.steps, embedded: true },
          }));
        } else if (evt.event === "enrichment") {
          setStreamPanelState((prev) => ({
            ...prev,
            enrichment: {
              suggested_title:
                typeof evt.data.suggested_title === "string" ? evt.data.suggested_title : null,
              summary: typeof evt.data.summary === "string" ? evt.data.summary : null,
              suggested_tags: readStringArray(evt.data.suggested_tags),
              suggested_topic:
                typeof evt.data.suggested_topic === "string" ? evt.data.suggested_topic : null,
            },
            steps: { ...prev.steps, enriched: true },
          }));
        } else if (evt.event === "bloom_inferred") {
          setStreamPanelState((prev) => ({
            ...prev,
            bloom: {
              level: Number(evt.data.level ?? 0),
              rationale: String(evt.data.rationale ?? ""),
            },
          }));
        } else if (evt.event === "error") {
          const msg = String(evt.data.message ?? evt.data.error ?? "stream error");
          setStreamError(msg);
          setStreamPhase("error");
          setStreamPanelState((prev) => ({
            ...prev,
            phase: "error",
            errors: [
              ...prev.errors,
              {
                step: String(evt.data.step ?? "stream"),
                message: msg,
              },
            ],
          }));
        } else if (evt.event === "done") {
          const finalCard = evt.data.card as Record<string, unknown> | null;
          setStreamPanelState((prev) => ({
            ...prev,
            phase: prev.errors.length > 0 ? "error" : "complete",
            cardId: Number(finalCard?.id ?? finalCardId ?? prev.cardId) || prev.cardId,
            title: String(finalCard?.title ?? finalTitle ?? prev.title ?? derivedTitle),
            steps: { ...prev.steps, completed: true },
          }));
        }
      }

      if (finalCardId && finalCardId > 0) {
        setSavedCardId(finalCardId);
        setStreamPhase("saved");
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
      const msg = err instanceof Error ? err.message : String(err);
      setStreamError(msg);
      setStreamPhase("error");
      setStreamPanelState((prev) => ({
        ...prev,
        phase: "error",
        errors: [...prev.errors, { step: "connection", message: msg }],
      }));
      console.warn("creation stream failed", err);
    } finally {
      streamInFlightRef.current = false;
      abortKey(abortKeyForDraft);
    }
  }, [
    activeDraft,
    sessionId,
    sharedContext.topic,
    sharedContext.tags,
    registerAbortController,
    abortKey,
    persistActiveDraft,
    promoteDraftToSaved,
    setSavedCardAnalysis,
    wordCount,
  ]);

  // Schedule a pause-save every time the draft content changes.
  useEffect(() => {
    if (!isEditingDraft || !activeDraft) return;
    if (pauseTimer.current) clearTimeout(pauseTimer.current);

    const streamKey = getDraftStreamKey(activeDraft);
    if (streamInFlightRef.current || lastStartedStreamKeyRef.current === streamKey) {
      return;
    }

    // Signal that we're queued for the AI stream — visible in the status chip.
    if ((activeDraft.content.trim().length ?? 0) >= MIN_STREAM_CHARS) {
      setStreamPhase("pending");
      setStreamPanelState((prev) => {
        if (prev.phase === "streaming") return prev;
        return {
          ...createInitialStreamPanelState(),
          phase: "pending",
          title: activeDraft.title.trim() || "Queued zettel",
        };
      });
    }
    pauseTimer.current = setTimeout(async () => {
      await kickCreationStream();
    }, PAUSE_MS);
    return () => {
      if (pauseTimer.current) clearTimeout(pauseTimer.current);
    };
  }, [isEditingDraft, activeDraft, activeDraft?.content, kickCreationStream]);

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
      const next = activeDraft.content ? `${activeDraft.content}\n\n${text}` : text;
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
      const nextIdx =
        cmd === "next" ? Math.min(stackOrder.length - 1, idx + 1) : Math.max(0, idx - 1);
      focusEntry(stackOrder[nextIdx] ?? null);
    },
    [stackOrder, focusedEntry, focusEntry, kickCreationStream, startDraft],
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
    streamPhase === "streaming"
      ? "AI DRAFTING..."
      : streamPhase === "pending"
        ? "AI PAUSED"
        : streamPhase === "saved"
          ? `SAVED ${savedCardId ? `· #${savedCardId}` : ""}`
          : streamPhase === "error"
            ? `ERROR · ${streamError?.slice(0, 40) ?? ""}`
            : isEditingDraft && activeDraft
              ? activeDraft.content.trim().length < MIN_STREAM_CHARS
                ? "DRAFT"
                : "READY"
              : focusedSaved
                ? focusedSaved.phase.toUpperCase()
                : "IDLE";

  // --- AI one-shot drafter state ---
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiGenerating, setAiGenerating] = useState(false);
  const showAiDrafter =
    isEditingDraft &&
    activeDraft !== null &&
    activeDraft.content.trim().length === 0 &&
    activeDraft.title.trim().length === 0;

  const handleAiDraft = useCallback(async () => {
    if (!aiPrompt.trim() || !activeDraft) return;
    setAiGenerating(true);
    try {
      const draft = await apiPostJson<
        { title: string; content: string; summary?: string; tags?: string[]; topic?: string },
        { prompt: string; topic?: string; tags?: string[] }
      >(`${apiRoutes.zettels.generate}/preview`, {
        prompt: aiPrompt.trim(),
        topic: sharedContext.topic,
        tags: sharedContext.tags.length ? sharedContext.tags : undefined,
      });
      if (draft.title) updateDraftTitle(draft.title);
      if (draft.content) updateDraftContent(draft.content);
      setAiPrompt("");
      // The pause-save effect will auto-kick on the new content.
    } catch (err) {
      toast.error("AI draft failed", {
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setAiGenerating(false);
    }
  }, [
    aiPrompt,
    activeDraft,
    sharedContext.topic,
    sharedContext.tags,
    updateDraftTitle,
    updateDraftContent,
  ]);

  return (
    <div className={cn("flex flex-col gap-6", className)} onPasteCapture={handlePaste}>
      {/* Title */}
      {isEditingDraft ? (
        <input
          value={title}
          onChange={(e) => updateDraftTitle(e.target.value)}
          placeholder="Untitled card"
          className="text-foreground placeholder:text-muted-foreground w-full border-none bg-transparent font-serif text-[42px] leading-[1.15] focus:outline-none"
          aria-label="Card title"
        />
      ) : (
        <h1 className="text-foreground font-serif text-[42px] leading-[1.15]">
          {title || "Untitled card"}
        </h1>
      )}

      {/* AI draft affordance — only on empty drafts */}
      {showAiDrafter && (
        <div className="rounded-md border border-dashed border-[var(--alfred-ruled-line)] bg-[var(--alfred-accent-subtle)]/40 p-4">
          <div className="text-primary mb-2 flex items-center gap-2 font-mono text-[10px] tracking-wider uppercase">
            <Sparkles className="size-3" />
            <span>Draft with AI</span>
          </div>
          <div className="flex items-start gap-2">
            <input
              value={aiPrompt}
              onChange={(e) => setAiPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && aiPrompt.trim()) {
                  e.preventDefault();
                  void handleAiDraft();
                }
              }}
              placeholder="Idea, question, or paste a concept — press Enter"
              disabled={aiGenerating}
              className="text-foreground placeholder:text-muted-foreground flex-1 border-none bg-transparent font-sans text-[14px] focus:outline-none"
              aria-label="AI draft prompt"
            />
            <button
              type="button"
              onClick={() => void handleAiDraft()}
              disabled={!aiPrompt.trim() || aiGenerating}
              className="border-primary/30 bg-primary/10 text-primary hover:bg-primary/20 rounded border px-3 py-1.5 font-mono text-[10px] tracking-wider uppercase transition-colors disabled:cursor-not-allowed disabled:opacity-50"
            >
              {aiGenerating ? "Drafting..." : "Draft"}
            </button>
          </div>
          <div className="mt-1.5 font-mono text-[9px] tracking-wider text-[var(--alfred-text-tertiary)] uppercase">
            Or just start writing below — AI connections stream in as you pause.
          </div>
        </div>
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
          <div className="text-foreground font-serif text-[17px] leading-[1.6] whitespace-pre-wrap">
            {content || (
              <span className="text-muted-foreground">This card has no content yet.</span>
            )}
          </div>
        )}
      </div>

      {/* Ruled divider + Bloom ladder + chips */}
      <div className="flex items-center gap-6 border-t border-[var(--alfred-ruled-line)] pt-4">
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
              "ml-1 font-mono text-[10px] tracking-wider uppercase",
              BLOOM_COLOR_CLASSES[bloomLevel],
            )}
          >
            {BLOOM_LABELS[bloomLevel]}
          </span>
        </div>

        {sharedContext.topic && (
          <span className="text-primary rounded bg-[var(--alfred-accent-muted)] px-2 py-0.5 font-sans text-[10px] tracking-wide uppercase">
            {sharedContext.topic}
          </span>
        )}
        {sharedContext.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {sharedContext.tags.map((tag) => (
              <span
                key={tag}
                className="text-muted-foreground rounded border border-[var(--alfred-ruled-line)] px-2 py-0.5 font-sans text-[10px] tracking-wide uppercase"
              >
                #{tag}
              </span>
            ))}
          </div>
        )}
      </div>

      <ZettelCreationStreamPanel state={streamPanelState} />

      {/* Status line */}
      <div className="flex justify-end font-mono text-[10px] tracking-wider text-[var(--alfred-text-tertiary)] uppercase">
        {phaseLabel} - {wordCount}W - {linkCount} {linkCount === 1 ? "LINK" : "LINKS"}
      </div>
    </div>
  );
}
