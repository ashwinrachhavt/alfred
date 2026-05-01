"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Sparkles, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useCardSearch } from "@/features/zettels/queries";

export type WikiLinkSelection = {
  cardId: number;
  title: string;
};

export type WikiLinkAutocompleteItem = WikiLinkSelection & {
  type: "ai" | "text";
  topic?: string | null;
};

type Props = {
  query: string;
  position: { top: number; left: number };
  contextCardId?: number;
  activeIndex: number;
  onSelect: (selection: WikiLinkSelection) => void;
  onCreateStub: (title: string) => void;
  onItemsChange?: (items: WikiLinkAutocompleteItem[], createTitle: string | null) => void;
  onClose: () => void;
};

export function WikiLinkAutocomplete({
  query,
  position,
  contextCardId,
  activeIndex,
  onSelect,
  onCreateStub,
  onItemsChange,
}: Props) {
  const [debouncedQuery, setDebouncedQuery] = useState(query.trim());
  const { data, isLoading, isError } = useCardSearch(
    debouncedQuery.length > 0 ? debouncedQuery : null,
    contextCardId,
  );
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 140);
    return () => window.clearTimeout(timer);
  }, [query]);

  // Build combined items list for keyboard navigation
  const textMatches = useMemo(() => data?.text_matches ?? [], [data?.text_matches]);
  const aiSuggestions = useMemo(() => data?.ai_suggestions ?? [], [data?.ai_suggestions]);
  const hasResults = textMatches.length > 0 || aiSuggestions.length > 0;

  // Combined list: AI suggestions first, then text matches
  const allItems = useMemo(
    () => [
      ...aiSuggestions.map((s) => ({
        cardId: s.id,
        title: s.title,
        type: "ai" as const,
        score: s.score,
        topic: s.topic,
      })),
      ...textMatches.map((m) => ({
        cardId: m.id,
        title: m.title,
        type: "text" as const,
        score: undefined as number | undefined,
        topic: m.topic,
      })),
    ],
    [aiSuggestions, textMatches],
  );

  // Deduplicate by id (AI version takes priority)
  const dedupedItems = useMemo(() => {
    const seenIds = new Set<number>();
    return allItems.filter((item) => {
      if (seenIds.has(item.cardId)) return false;
      seenIds.add(item.cardId);
      return true;
    });
  }, [allItems]);

  const createTitle = !hasResults && !isLoading && query.trim().length > 0 ? query.trim() : null;

  useEffect(() => {
    onItemsChange?.(dedupedItems, createTitle);
  }, [createTitle, dedupedItems, onItemsChange]);

  const safePosition = useMemo(() => {
    if (typeof window === "undefined") return position;
    return {
      top: Math.max(12, Math.min(position.top, window.innerHeight - 360)),
      left: Math.max(12, Math.min(position.left, window.innerWidth - 332)),
    };
  }, [position]);

  // Scroll active item into view
  useEffect(() => {
    if (!containerRef.current) return;
    const active = containerRef.current.querySelector("[data-active=true]");
    active?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  return (
    <div
      ref={containerRef}
      className="bg-card animate-in fade-in zoom-in-95 fixed z-50 w-80 overflow-hidden rounded-lg border shadow-xl duration-100"
      style={{ top: `${safePosition.top}px`, left: `${safePosition.left}px` }}
      onMouseDown={(e) => e.preventDefault()}
    >
      {/* Loading state */}
      {isLoading && !data && (
        <div className="flex items-center gap-2 px-3 py-3">
          <Loader2 className="text-muted-foreground h-3.5 w-3.5 animate-spin" />
          <span className="text-muted-foreground text-xs">Searching cards...</span>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="text-destructive px-3 py-3 text-xs">Search unavailable. Try again.</div>
      )}

      {/* Results */}
      {data && (
        <div className="max-h-72 overflow-y-auto p-1">
          {/* AI suggestions section */}
          {aiSuggestions.length > 0 && (
            <>
              <div className="flex items-center gap-1.5 px-2 py-1">
                <Sparkles className="text-primary h-3 w-3" />
                <span className="text-primary text-[10px] font-medium uppercase">
                  AI Recommended
                </span>
              </div>
              {aiSuggestions.map((s) => {
                const globalIdx = dedupedItems.findIndex((d) => d.cardId === s.id);
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
                        ? "text-foreground bg-[var(--alfred-accent-subtle)]"
                        : "text-muted-foreground hover:text-foreground hover:bg-[var(--alfred-accent-subtle)]",
                    )}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm">{s.title}</div>
                      {s.topic && (
                        <div className="text-[9px] text-[var(--alfred-text-tertiary)] uppercase">
                          {s.topic}
                        </div>
                      )}
                    </div>
                    <span className="text-primary ml-2 shrink-0 rounded bg-[var(--alfred-accent-subtle)] px-1.5 py-0.5 text-[9px] font-medium">
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
                <Sparkles className="text-primary h-3 w-3 animate-pulse" />
                <span className="text-primary text-[10px] font-medium uppercase opacity-60">
                  Finding AI suggestions...
                </span>
              </div>
            </div>
          )}

          {/* Text matches section */}
          {textMatches.length > 0 && (
            <>
              <div className="px-2 py-1">
                <span className="text-muted-foreground text-[10px] font-medium uppercase">
                  Cards
                </span>
              </div>
              {textMatches.map((m) => {
                const globalIdx = dedupedItems.findIndex((d) => d.cardId === m.id);
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
                        ? "text-foreground bg-[var(--alfred-accent-subtle)]"
                        : "text-muted-foreground hover:text-foreground hover:bg-[var(--alfred-accent-subtle)]",
                    )}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm">{m.title}</div>
                      {m.topic && (
                        <div className="text-[9px] text-[var(--alfred-text-tertiary)] uppercase">
                          {m.topic}
                        </div>
                      )}
                    </div>
                    <span className="ml-2 text-[9px] text-[var(--alfred-text-tertiary)] uppercase">
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
                  ? "text-foreground bg-[var(--alfred-accent-subtle)]"
                  : "text-muted-foreground hover:text-foreground hover:bg-[var(--alfred-accent-subtle)]",
              )}
            >
              <Plus className="text-primary h-3.5 w-3.5" />
              <span className="text-sm">
                Create &ldquo;<span className="text-foreground font-medium">{query}</span>&rdquo;
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
        <kbd className="rounded border px-1">↑↓</kbd> navigate{" "}
        <kbd className="rounded border px-1">↵</kbd> select{" "}
        <kbd className="rounded border px-1">esc</kbd> close
      </div>
    </div>
  );
}
