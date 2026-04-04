"use client";

import { useEffect, useRef } from "react";
import { Loader2, Sparkles, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useCardSearch } from "@/features/zettels/queries";

export type WikiLinkSelection = {
  cardId: number;
  title: string;
};

type Props = {
  query: string;
  position: { top: number; left: number };
  contextCardId?: number;
  activeIndex: number;
  onSelect: (selection: WikiLinkSelection) => void;
  onCreateStub: (title: string) => void;
  onClose: () => void;
};

export function WikiLinkAutocomplete({
  query,
  position,
  contextCardId,
  activeIndex,
  onSelect,
  onCreateStub,
}: Props) {
  const { data, isLoading, isError } = useCardSearch(
    query.length > 0 ? query : null,
    contextCardId,
  );
  const containerRef = useRef<HTMLDivElement>(null);

  // Build combined items list for keyboard navigation
  const textMatches = data?.text_matches ?? [];
  const aiSuggestions = data?.ai_suggestions ?? [];
  const hasResults = textMatches.length > 0 || aiSuggestions.length > 0;

  // Combined list: AI suggestions first, then text matches
  const allItems = [
    ...aiSuggestions.map((s) => ({
      id: s.id,
      title: s.title,
      type: "ai" as const,
      score: s.score,
      topic: s.topic,
    })),
    ...textMatches.map((m) => ({
      id: m.id,
      title: m.title,
      type: "text" as const,
      score: undefined as number | undefined,
      topic: m.topic,
    })),
  ];

  // Deduplicate by id (AI version takes priority)
  const seenIds = new Set<number>();
  const dedupedItems = allItems.filter((item) => {
    if (seenIds.has(item.id)) return false;
    seenIds.add(item.id);
    return true;
  });

  // Scroll active item into view
  useEffect(() => {
    if (!containerRef.current) return;
    const active = containerRef.current.querySelector("[data-active=true]");
    active?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  return (
    <div
      ref={containerRef}
      className="fixed z-50 w-80 overflow-hidden rounded-lg border bg-card shadow-xl animate-in fade-in zoom-in-95 duration-100"
      style={{ top: `${position.top}px`, left: `${position.left}px` }}
      onMouseDown={(e) => e.preventDefault()}
    >
      {/* Loading state */}
      {isLoading && !data && (
        <div className="flex items-center gap-2 px-3 py-3">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
          <span className="text-xs text-muted-foreground">Searching cards...</span>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="px-3 py-3 text-xs text-destructive">
          Search unavailable. Try again.
        </div>
      )}

      {/* Results */}
      {data && (
        <div className="max-h-72 overflow-y-auto p-1">
          {/* AI suggestions section */}
          {aiSuggestions.length > 0 && (
            <>
              <div className="flex items-center gap-1.5 px-2 py-1">
                <Sparkles className="h-3 w-3 text-primary" />
                <span className="text-[10px] font-medium uppercase tracking-wider text-primary">
                  AI Recommended
                </span>
              </div>
              {aiSuggestions.map((s) => {
                const globalIdx = dedupedItems.findIndex((d) => d.id === s.id);
                return (
                  <button
                    key={`ai-${s.id}`}
                    type="button"
                    data-active={globalIdx === activeIndex}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      onSelect({ cardId: s.id, title: s.title });
                    }}
                    className={cn(
                      "flex w-full items-center justify-between rounded-md px-3 py-1.5 text-left transition-colors",
                      globalIdx === activeIndex
                        ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                        : "text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
                    )}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm">{s.title}</div>
                      {s.topic && (
                        <div className="text-[9px] uppercase tracking-wide text-[var(--alfred-text-tertiary)]">
                          {s.topic}
                        </div>
                      )}
                    </div>
                    <span className="ml-2 shrink-0 rounded bg-[var(--alfred-accent-subtle)] px-1.5 py-0.5 text-[9px] font-medium text-primary">
                      {Math.round(s.score * 100)}%
                    </span>
                  </button>
                );
              })}
            </>
          )}

          {/* Loading shimmer for AI when text results exist but AI is still loading */}
          {isLoading && textMatches.length > 0 && aiSuggestions.length === 0 && (
            <div className="space-y-1 px-2 py-1">
              <div className="flex items-center gap-1.5">
                <Sparkles className="h-3 w-3 text-primary animate-pulse" />
                <span className="text-[10px] font-medium uppercase tracking-wider text-primary opacity-60">
                  Finding AI suggestions...
                </span>
              </div>
            </div>
          )}

          {/* Text matches section */}
          {textMatches.length > 0 && (
            <>
              <div className="px-2 py-1">
                <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  Cards
                </span>
              </div>
              {textMatches.map((m) => {
                const globalIdx = dedupedItems.findIndex((d) => d.id === m.id);
                if (globalIdx === -1) return null; // deduped out
                return (
                  <button
                    key={`text-${m.id}`}
                    type="button"
                    data-active={globalIdx === activeIndex}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      onSelect({ cardId: m.id, title: m.title });
                    }}
                    className={cn(
                      "flex w-full items-center justify-between rounded-md px-3 py-1.5 text-left transition-colors",
                      globalIdx === activeIndex
                        ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                        : "text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
                    )}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm">{m.title}</div>
                      {m.topic && (
                        <div className="text-[9px] uppercase tracking-wide text-[var(--alfred-text-tertiary)]">
                          {m.topic}
                        </div>
                      )}
                    </div>
                    <span className="ml-2 text-[9px] uppercase text-[var(--alfred-text-tertiary)]">
                      {m.status === "stub" ? "stub" : ""}
                    </span>
                  </button>
                );
              })}
            </>
          )}

          {/* No results + create stub option */}
          {!hasResults && !isLoading && query.length > 0 && (
            <button
              type="button"
              data-active={activeIndex === 0}
              onMouseDown={(e) => {
                e.preventDefault();
                onCreateStub(query);
              }}
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left transition-colors",
                activeIndex === 0
                  ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                  : "text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
              )}
            >
              <Plus className="h-3.5 w-3.5 text-primary" />
              <span className="text-sm">
                Create &ldquo;<span className="font-medium text-foreground">{query}</span>&rdquo;
              </span>
            </button>
          )}

          {/* Empty query — show recent cards */}
          {!hasResults && !isLoading && query.length === 0 && (
            <div className="px-3 py-2 text-[11px] text-[var(--alfred-text-tertiary)]">
              Type to search cards...
            </div>
          )}
        </div>
      )}

      {/* Keyboard hint */}
      <div className="border-t px-3 py-1.5 text-[9px] text-[var(--alfred-text-tertiary)]">
        <kbd className="rounded border px-1">↑↓</kbd> navigate
        {" "}
        <kbd className="rounded border px-1">↵</kbd> select
        {" "}
        <kbd className="rounded border px-1">esc</kbd> close
      </div>
    </div>
  );
}
