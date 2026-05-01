"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Search, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";

import {
  ENTRY_KIND_OPTIONS,
  ENTRY_STATUS_OPTIONS,
  parseFiltersFromSearchParams,
  serializeFiltersToQueryString,
  toggleMultiValue,
  type FilterKind,
  type FilterStatus,
  type TodayFilterState,
} from "./filter-state";

const CHIP_BASE =
  "inline-flex items-center justify-center rounded-sm border border-[var(--alfred-ruled-line)] bg-transparent px-2.5 py-1 text-[11px] uppercase tracking-widest transition-colors select-none cursor-pointer";
const CHIP_OFF = "text-[var(--alfred-text-tertiary)] hover:text-foreground";
const CHIP_ON =
  "bg-[var(--alfred-accent-subtle)] text-foreground font-medium border-[var(--alfred-accent-muted)]";

const GROUP_LABEL =
  "text-[10px] uppercase tracking-widest font-medium text-[var(--alfred-text-tertiary)] mr-1";

export function EntryFilterBar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const filters = parseFiltersFromSearchParams(searchParams);

  // Local draft state for the search input so we can debounce URL writes.
  // React 19 idiom for "reset state when URL changes": store the last-seen URL
  // value alongside the draft and compare it during render.
  const urlQ = filters.q ?? "";
  const [searchState, setSearchState] = useState<{ draft: string; seenUrlQ: string }>(
    () => ({ draft: urlQ, seenUrlQ: urlQ }),
  );
  // If the URL's q changed out from under us (back-button, other tab wrote it,
  // etc.), reset the draft. This is the recommended React 19 pattern — see
  // https://react.dev/reference/react/useState#storing-information-from-previous-renders
  const searchDraft =
    searchState.seenUrlQ === urlQ
      ? searchState.draft
      : (setSearchState({ draft: urlQ, seenUrlQ: urlQ }), urlQ);
  const setSearchDraft = useCallback(
    (v: string) => {
      setSearchState((prev) => ({ ...prev, draft: v }));
    },
    [],
  );
  // Local draft state for tag input so users can type without the URL flashing.
  const [tagDraft, setTagDraft] = useState("");
  const searchTimeoutRef = useRef<number | null>(null);

  const writeFilters = useCallback(
    (next: TodayFilterState) => {
      const qs = serializeFiltersToQueryString(next);
      router.replace(qs ? `/today?${qs}` : "/today");
    },
    [router],
  );

  const onToggleKind = useCallback(
    (value: FilterKind) => {
      writeFilters({ ...filters, kind: toggleMultiValue(filters.kind, value) });
    },
    [filters, writeFilters],
  );

  const onToggleStatus = useCallback(
    (value: FilterStatus) => {
      writeFilters({ ...filters, status: toggleMultiValue(filters.status, value) });
    },
    [filters, writeFilters],
  );

  const onRemoveTag = useCallback(
    (value: string) => {
      writeFilters({ ...filters, tag: filters.tag.filter((t) => t !== value) });
    },
    [filters, writeFilters],
  );

  const onAddTag = useCallback(
    (raw: string) => {
      const cleaned = raw.trim().toLowerCase();
      if (!cleaned) return;
      if (filters.tag.includes(cleaned)) {
        setTagDraft("");
        return;
      }
      writeFilters({ ...filters, tag: [...filters.tag, cleaned] });
      setTagDraft("");
    },
    [filters, writeFilters],
  );

  const onToggleTodosOnly = useCallback(() => {
    writeFilters({ ...filters, todosOnly: !filters.todosOnly });
  }, [filters, writeFilters]);

  const onSearchChange = useCallback(
    (raw: string) => {
      setSearchDraft(raw);
      if (searchTimeoutRef.current !== null) {
        window.clearTimeout(searchTimeoutRef.current);
      }
      searchTimeoutRef.current = window.setTimeout(() => {
        const trimmed = raw.trim();
        writeFilters({ ...filters, q: trimmed.length > 0 ? trimmed : null });
      }, 200);
    },
    [filters, setSearchDraft, writeFilters],
  );

  // Clean up the debounce on unmount to avoid stray timeouts.
  useEffect(
    () => () => {
      if (searchTimeoutRef.current !== null) {
        window.clearTimeout(searchTimeoutRef.current);
      }
    },
    [],
  );

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-[var(--alfred-ruled-line)] pb-3">
      {/* Kind chips */}
      <div className="flex items-center gap-1.5">
        <span className={GROUP_LABEL}>Kind</span>
        {ENTRY_KIND_OPTIONS.map((opt) => {
          const active = filters.kind.includes(opt.value);
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onToggleKind(opt.value)}
              aria-pressed={active}
              className={cn(CHIP_BASE, active ? CHIP_ON : CHIP_OFF)}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      {/* Status chips */}
      <div className="flex items-center gap-1.5">
        <span className={GROUP_LABEL}>Status</span>
        {ENTRY_STATUS_OPTIONS.map((opt) => {
          const active = filters.status.includes(opt.value);
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onToggleStatus(opt.value)}
              aria-pressed={active}
              className={cn(CHIP_BASE, active ? CHIP_ON : CHIP_OFF)}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      {/* Tags */}
      <div className="flex items-center gap-1.5 min-w-0">
        <span className={GROUP_LABEL}>Tags</span>
        <input
          type="text"
          value={tagDraft}
          onChange={(e) => setTagDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              onAddTag(tagDraft);
            } else if (
              e.key === "Backspace" &&
              tagDraft.length === 0 &&
              filters.tag.length > 0
            ) {
              onRemoveTag(filters.tag[filters.tag.length - 1]);
            }
          }}
          placeholder="add tag…"
          className="h-7 w-24 rounded-sm border border-[var(--alfred-ruled-line)] bg-transparent px-2 font-mono text-[11px] text-foreground placeholder:text-[var(--alfred-text-tertiary)] focus-visible:border-ring focus-visible:outline-none"
        />
        {filters.tag.map((t) => (
          <span
            key={t}
            className="inline-flex items-center gap-1 rounded-sm bg-[var(--alfred-accent-muted)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-foreground"
          >
            {t}
            <button
              type="button"
              onClick={() => onRemoveTag(t)}
              className="inline-flex items-center justify-center rounded-sm text-[var(--alfred-text-tertiary)] hover:text-foreground"
              aria-label={`Remove tag ${t}`}
            >
              <X className="size-3" aria-hidden="true" />
            </button>
          </span>
        ))}
      </div>

      {/* Flexible spacer */}
      <div className="flex-1" />

      {/* Search */}
      <div className="relative">
        <Search
          className="absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-[var(--alfred-text-tertiary)]"
          aria-hidden="true"
        />
        <Input
          value={searchDraft}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search titles…"
          className="h-8 w-56 rounded-sm border-[var(--alfred-ruled-line)] pl-7 text-sm"
          aria-label="Search entries by title"
        />
      </div>

      {/* Todos only toggle */}
      <label className="inline-flex items-center gap-2 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={filters.todosOnly}
          onChange={onToggleTodosOnly}
          className="sr-only peer"
        />
        <span
          className={cn(
            "inline-flex h-4 w-7 items-center rounded-full border border-[var(--alfred-ruled-line)] px-0.5 transition-colors",
            filters.todosOnly
              ? "bg-[var(--alfred-text-tertiary)] border-[var(--alfred-text-tertiary)]"
              : "bg-transparent",
          )}
          aria-hidden="true"
        >
          <span
            className={cn(
              "inline-block size-3 rounded-full bg-background transition-transform",
              filters.todosOnly ? "translate-x-3" : "translate-x-0",
            )}
          />
        </span>
        <span
          className={cn(
            "text-[10px] font-medium uppercase tracking-widest",
            filters.todosOnly ? "text-foreground" : "text-[var(--alfred-text-tertiary)]",
          )}
        >
          Todos only
        </span>
      </label>
    </div>
  );
}
