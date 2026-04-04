"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { searchZettelCards, type ZettelSearchResult } from "@/lib/api/zettels";

type Props = {
  query: string;
  position: { top: number; left: number };
  onSelect: (card: ZettelSearchResult) => void;
  onClose: () => void;
};

export function WikiLinkAutocomplete({ query, position, onSelect, onClose }: Props) {
  const [results, setResults] = useState<ZettelSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const activeIndexRef = useRef(0);
  const hasFetched = useRef(false);

  // Search on query change — including empty query (shows recent cards like Obsidian)
  useEffect(() => {
    setIsLoading(true);
    const delay = hasFetched.current ? 150 : 0; // no delay on first open
    hasFetched.current = true;

    const timer = setTimeout(async () => {
      try {
        const cards = await searchZettelCards(query, 8);
        setResults(cards);
        setActiveIndex(0);
        activeIndexRef.current = 0;
      } catch {
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, delay);

    return () => clearTimeout(timer);
  }, [query]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
        return;
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        e.stopPropagation();
        const next = (activeIndexRef.current + 1) % Math.max(1, results.length);
        activeIndexRef.current = next;
        setActiveIndex(next);
        return;
      }

      if (e.key === "ArrowUp") {
        e.preventDefault();
        e.stopPropagation();
        const next = (activeIndexRef.current - 1 + results.length) % Math.max(1, results.length);
        activeIndexRef.current = next;
        setActiveIndex(next);
        return;
      }

      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        e.stopPropagation();
        if (results.length > 0) {
          const idx = Math.min(activeIndexRef.current, results.length - 1);
          onSelect(results[idx]);
        }
        return;
      }
    },
    [results, onSelect, onClose],
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown, true);
    return () => document.removeEventListener("keydown", handleKeyDown, true);
  }, [handleKeyDown]);

  useEffect(() => {
    activeIndexRef.current = activeIndex;
  }, [activeIndex]);

  const isEmptyQuery = !query.trim();

  return (
    <div
      ref={containerRef}
      className="fixed z-50 w-80 overflow-hidden rounded-md border bg-card shadow-lg animate-in fade-in zoom-in-95 duration-100"
      style={{ top: `${position.top}px`, left: `${position.left}px` }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 border-b px-3 py-1.5">
        <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
          {isEmptyQuery ? "Recent cards" : "Link to card"}
        </span>
        {isLoading && <Loader2 className="size-3 animate-spin text-muted-foreground" />}
      </div>

      {/* Results */}
      <div className="max-h-64 overflow-y-auto p-1">
        {results.length > 0 ? (
          results.map((card, idx) => (
            <button
              key={card.id}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                onSelect(card);
              }}
              className={cn(
                "flex w-full flex-col gap-0.5 rounded-md px-3 py-2 text-left transition-colors",
                idx === activeIndex
                  ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                  : "text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
              )}
            >
              <span className="text-sm font-medium truncate">{card.title}</span>
              <div className="flex items-center gap-1.5">
                {card.topic && (
                  <span className="text-[9px] text-[var(--alfred-text-tertiary)]">{card.topic}</span>
                )}
                {card.status === "draft" && (
                  <span className="rounded border border-dashed border-[var(--alfred-text-tertiary)] px-1 py-px text-[8px] uppercase text-[var(--alfred-text-tertiary)]">
                    draft
                  </span>
                )}
              </div>
            </button>
          ))
        ) : !isLoading ? (
          <div className="px-3 py-3 text-center text-[11px] text-[var(--alfred-text-tertiary)]">
            {query.trim() ? `No cards found for "${query}"` : "No cards yet"}
          </div>
        ) : null}
      </div>

      {/* Footer hint */}
      <div className="border-t px-3 py-1.5">
        <span className="text-[9px] text-[var(--alfred-text-tertiary)]">
          ↑↓ navigate · Enter select · Esc close
        </span>
      </div>
    </div>
  );
}
