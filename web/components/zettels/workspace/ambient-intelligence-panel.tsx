"use client";

/**
 * AmbientIntelligencePanel (T10)
 *
 * Right column of the Zettel Workspace. Surfaces analysis for the focused entry:
 *  - Bloom prompt (gated behind 60+ words)
 *  - Connection suggestions
 *  - Enrichment retry on failure
 *  - Decomposition CTA when drafts grow long
 *
 * Pure read-surface except for the retry button and the "Answer inline" CTA,
 * which publishes text to the editor bus.
 */

import { useMemo } from "react";

import { cn } from "@/lib/utils";
import {
  BLOOM_BG_CLASSES,
  BLOOM_LABELS,
  pickBloomQuestion,
  type BloomLevel,
} from "@/lib/bloom";
import {
  useZettelWorkspaceStore,
  type SavedCardState,
} from "@/lib/stores/zettel-workspace-store";
import { publishEditorInsert } from "@/components/zettels/workspace/editor-bus";
import { useWorkspaceContext } from "@/components/zettels/workspace/workspace-context";
import { useResumeEnrichment } from "@/features/workspace/mutations";

type Props = {
  className?: string;
};

function countWords(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) return 0;
  return trimmed.split(/\s+/).length;
}

function Divider() {
  return (
    <div className="border-t border-[var(--alfred-ruled-line)] my-4" />
  );
}

export function AmbientIntelligencePanel({ className }: Props) {
  const sessionId = useZettelWorkspaceStore((s) => s.sessionId);
  const focusedEntry = useZettelWorkspaceStore((s) => s.focusedEntry);
  const activeDraft = useZettelWorkspaceStore((s) => s.activeDraft);
  const savedCards = useZettelWorkspaceStore((s) => s.savedCards);
  const setSavedCardPhase = useZettelWorkspaceStore(
    (s) => s.setSavedCardPhase,
  );
  const setSavedCardAnalysis = useZettelWorkspaceStore(
    (s) => s.setSavedCardAnalysis,
  );
  const { openDecomposition } = useWorkspaceContext();
  const resumeEnrichment = useResumeEnrichment(sessionId);

  // Resolve the focused saved card (if any).
  const focusedSaved: SavedCardState | null = useMemo(() => {
    if (!focusedEntry || focusedEntry.type !== "saved") return null;
    return savedCards.get(focusedEntry.id) ?? null;
  }, [focusedEntry, savedCards]);

  const focusedIsDraft =
    focusedEntry?.type === "draft" &&
    !!activeDraft &&
    activeDraft.clientId === focusedEntry.clientId;

  const content = focusedIsDraft
    ? (activeDraft?.content ?? "")
    : (focusedSaved?.content ?? "");
  const wordCount = countWords(content);

  const bloomLevel: BloomLevel = (focusedIsDraft
    ? (activeDraft?.bloom?.inferredLevel ?? 1)
    : (focusedSaved?.bloom.inferredLevel ?? 1)) as BloomLevel;

  const showBloomPrompt = wordCount >= 60;
  const bloomQuestion = showBloomPrompt
    ? pickBloomQuestion(bloomLevel, wordCount)
    : null;

  // Connections from the focused analysis, if any.
  const analysis = focusedIsDraft ? null : (focusedSaved?.analysis ?? null);
  const connections = analysis?.connections ?? [];

  const enrichmentError = focusedSaved?.enrichmentLastError ?? null;

  // Decomposition CTA — only for active drafts that have grown long.
  const showDecomposeCta =
    focusedIsDraft && !!activeDraft && activeDraft.content.length > 500;

  const handleRetryEnrichment = async () => {
    if (!focusedSaved) return;
    try {
      await resumeEnrichment.mutateAsync(focusedSaved.id);
      // Clear the error on success. The store has no dedicated error-clear action
      // (setSavedCardEnrichmentError exists) but per spec we land on phase ready
      // and null out the enrichment analysis so a subsequent hydrate refreshes it.
      setSavedCardPhase(focusedSaved.id, "ready");
      if (focusedSaved.analysis) {
        setSavedCardAnalysis(focusedSaved.id, {
          ...focusedSaved.analysis,
          enrichment: null,
        });
      }
    } catch {
      // The mutation hook surfaces the error via its own state; keep the button visible.
    }
  };

  return (
    <aside
      className={cn("flex flex-col gap-4 px-5 py-5", className)}
      aria-label="Ambient intelligence"
    >
      {/* Bloom prompt */}
      {bloomQuestion && (
        <section>
          <div className="font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
            {`BLOOM · LEVEL ${bloomLevel} · ${BLOOM_LABELS[bloomLevel]}`}
          </div>
          <blockquote className="mt-2 font-serif italic text-[19px] leading-[1.45] text-foreground">
            {bloomQuestion}
          </blockquote>
          <button
            type="button"
            onClick={() =>
              publishEditorInsert(`> ${bloomQuestion}\n\n`)
            }
            className={cn(
              "mt-3 rounded border border-[var(--alfred-ruled-line)] px-3 py-1 font-mono text-[10px] font-medium uppercase tracking-wider text-foreground transition-colors hover:bg-accent",
            )}
          >
            Answer inline
          </button>
        </section>
      )}

      {bloomQuestion && <Divider />}

      {/* Connections */}
      <section>
        <div className="font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
          Connections
        </div>
        {connections.length === 0 ? (
          <div className="mt-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            Keep writing
          </div>
        ) : (
          <ul className="mt-2 flex flex-col gap-3">
            {connections.slice(0, 5).map((c) => {
              const score = Math.max(0, Math.min(1, Number(c.score) || 0));
              const opacity = 0.25 + score * 0.75;
              return (
                <li key={`${c.card_id}-${c.title}`} className="flex items-start gap-2">
                  <span
                    className={cn(
                      "mt-1.5 size-1.5 shrink-0 rounded-full",
                      BLOOM_BG_CLASSES[5],
                    )}
                    style={{ opacity }}
                    aria-hidden="true"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-serif text-[14px] text-foreground">
                      {c.title || "Untitled card"}
                    </div>
                    <div className="mt-0.5 font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
                      {c.reason || "related"}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* Enrichment state */}
      {enrichmentError && (
        <>
          <Divider />
          <section>
            <div className="font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
              Enrichment
            </div>
            <button
              type="button"
              onClick={handleRetryEnrichment}
              disabled={resumeEnrichment.isPending}
              className={cn(
                "mt-2 rounded border border-[var(--alfred-ruled-line)] px-3 py-1 text-left font-mono text-[10px] uppercase tracking-wider text-foreground transition-colors hover:bg-accent",
                "disabled:cursor-not-allowed disabled:opacity-60",
              )}
            >
              {resumeEnrichment.isPending
                ? "Retrying..."
                : `Retry enrichment (${enrichmentError})`}
            </button>
          </section>
        </>
      )}

      {/* Decomposition CTA */}
      {showDecomposeCta && activeDraft && (
        <>
          <Divider />
          <section>
            <button
              type="button"
              onClick={() =>
                openDecomposition({ rawText: activeDraft.content })
              }
              className="w-full rounded border border-[var(--alfred-ruled-line)] px-3 py-2 font-mono text-[10px] font-medium uppercase tracking-wider text-foreground transition-colors hover:bg-accent"
            >
              Review split
            </button>
          </section>
        </>
      )}
    </aside>
  );
}

export default AmbientIntelligencePanel;
