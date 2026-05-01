"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Search, Sparkles } from "lucide-react";

import { Input } from "@/components/ui/input";
import { searchCards, type CardSearchMatch } from "@/lib/api/zettels";
import { cn } from "@/lib/utils";

type Props = {
  fromCardId: number;
  value: number | null;
  onChange: (id: number | null, title?: string) => void;
  autoFocus?: boolean;
};

type ResultRow =
  | { kind: "text"; id: number; title: string; topic: string | null }
  | { kind: "ai"; id: number; title: string; topic: string | null; reason: string };

export function ZettelPicker({ fromCardId, value, onChange, autoFocus }: Props) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [rows, setRows] = useState<ResultRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [highlight, setHighlight] = useState(0);
  const [selectedTitle, setSelectedTitle] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(query), 150);
    return () => window.clearTimeout(id);
  }, [query]);

  useEffect(() => {
    let cancelled = false;
    const q = debounced.trim();
    if (q.length === 0) {
      setRows([]);
      setSearchError(null);
      return;
    }
    setLoading(true);
    setSearchError(null);
    searchCards(q, fromCardId)
      .then((res) => {
        if (cancelled) return;
        const text: ResultRow[] = res.text_matches
          .filter((c: CardSearchMatch) => c.id !== fromCardId)
          .map((c) => ({ kind: "text", id: c.id, title: c.title, topic: c.topic }));
        const ai: ResultRow[] = res.ai_suggestions
          .filter((c) => c.id !== fromCardId)
          .map((c) => ({
            kind: "ai",
            id: c.id,
            title: c.title,
            topic: c.topic,
            reason: c.reason,
          }));
        setRows([...text, ...ai]);
        setHighlight(0);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setRows([]);
        setSearchError(
          err instanceof Error && err.message ? err.message : "Search failed — try again",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debounced, fromCardId]);

  const selectedLabel = useMemo(() => {
    if (value == null) return null;
    return selectedTitle ?? `#${value}`;
  }, [value, selectedTitle]);

  const commit = (row: ResultRow) => {
    onChange(row.id, row.title);
    setSelectedTitle(row.title);
    setQuery("");
    setRows([]);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (rows.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => (h + 1) % rows.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => (h - 1 + rows.length) % rows.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      commit(rows[highlight]);
    }
  };

  if (value !== null) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-md border px-3 py-2">
        <span className="truncate text-sm">{selectedLabel}</span>
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground text-xs"
          onClick={() => {
            onChange(null);
            setSelectedTitle(null);
          }}
        >
          change
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="relative">
        <Search
          size={12}
          className="text-muted-foreground absolute top-1/2 left-2.5 -translate-y-1/2"
        />
        <Input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Search zettels by title..."
          className="pl-7 text-sm"
        />
        {loading && (
          <Loader2
            size={12}
            className="text-muted-foreground absolute top-1/2 right-2.5 -translate-y-1/2 animate-spin"
          />
        )}
      </div>
      {searchError && (
        <p role="alert" className="text-destructive mt-1 text-[11px]">
          {searchError}
        </p>
      )}
      {rows.length > 0 && (
        <div className="bg-popover absolute top-full right-0 left-0 z-50 mt-1 max-h-56 overflow-y-auto rounded-md border shadow-md">
          {rows.map((row, idx) => (
            <button
              key={`${row.kind}-${row.id}`}
              type="button"
              onMouseEnter={() => setHighlight(idx)}
              onClick={() => commit(row)}
              className={cn(
                "flex w-full items-center gap-2 px-3 py-2 text-left text-xs",
                highlight === idx && "bg-accent",
              )}
            >
              <span className="flex-1 truncate">{row.title}</span>
              {row.topic && (
                <span className="text-muted-foreground truncate text-[10px] uppercase">
                  {row.topic}
                </span>
              )}
              {row.kind === "ai" && (
                <Sparkles size={10} className="text-primary shrink-0" />
              )}
            </button>
          ))}
        </div>
      )}
      {!loading && !searchError && debounced.trim().length > 0 && rows.length === 0 && (
        <p className="text-muted-foreground mt-1 text-[11px]">
          No matching zettels found.
        </p>
      )}
    </div>
  );
}
