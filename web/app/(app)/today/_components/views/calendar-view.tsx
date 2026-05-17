"use client";

/**
 * COLOR BUDGET — Calendar View (Midnight Editorial)
 *
 * Accent #E8590C (bg-primary / text-primary / border-primary) appears ONLY:
 *   1. Today's cell — border-primary + text-primary on day number
 *   2. Selected day cell — bg-[var(--alfred-accent-subtle)] + text-primary
 *
 * Kind-density uses shape (· ○ ◇ ▪), NOT color. Entry counts are monochrome
 * Berkeley Mono. All grays via --alfred-* vars, never Tailwind gray scales.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  addDays,
  addMonths,
  differenceInCalendarDays,
  endOfMonth,
  format,
  isSameDay,
  isSameMonth,
  isToday,
  parseISO,
  startOfMonth,
  startOfWeek,
  subMonths,
} from "date-fns";
import { ChevronLeftIcon, ChevronRightIcon, PlusIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useBrowserTimeZone } from "@/lib/hooks/use-browser-timezone";
import { useTodayEntries, toIsoDay } from "@/features/today/queries";
import {
  filterStateToListParams,
  parseFiltersFromSearchParams,
} from "../filter-state";
import { useTodayInteraction } from "../today-interaction-context";
import type {
  DailyEntryItem,
  TodayEntryKind,
} from "@/features/today/types";

// ISO week (Monday start). date-fns `weekStartsOn: 1` maps to Monday.
const MONDAY_START = 1 as const;

// Order fixed so shapes map consistently across cells.
const KIND_ORDER: readonly TodayEntryKind[] = [
  "todo",
  "note",
  "learning",
  "artifact_ref",
] as const;

const KIND_GLYPH: Record<TodayEntryKind, string> = {
  todo: "·",
  note: "○",
  learning: "◇",
  artifact_ref: "▪",
};

const KIND_LABEL: Record<TodayEntryKind, string> = {
  todo: "todo",
  note: "note",
  learning: "learning",
  artifact_ref: "artifact",
};

const WEEKDAY_HEADERS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"] as const;

// ---------------------------------------------------------------------------
// Month math helpers
// ---------------------------------------------------------------------------

function parseMonthParam(raw: string | null | undefined): Date {
  if (raw) {
    const match = /^(\d{4})-(\d{2})$/.exec(raw);
    if (match) {
      const year = Number(match[1]);
      const monthIdx = Number(match[2]) - 1;
      if (!Number.isNaN(year) && monthIdx >= 0 && monthIdx <= 11) {
        return new Date(year, monthIdx, 1);
      }
    }
  }
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), 1);
}

function formatMonthParam(d: Date): string {
  return format(d, "yyyy-MM");
}

function parseDateParam(raw: string | null | undefined): Date | null {
  if (!raw) return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return null;
  try {
    const d = parseISO(raw);
    if (Number.isNaN(d.getTime())) return null;
    return d;
  } catch {
    return null;
  }
}

function buildMonthGrid(month: Date): Date[] {
  const gridStart = startOfWeek(startOfMonth(month), { weekStartsOn: MONDAY_START });
  const cells: Date[] = [];
  for (let i = 0; i < 42; i += 1) {
    cells.push(addDays(gridStart, i));
  }
  return cells;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface CalendarViewProps {
  month?: string;
}

export function CalendarView({ month: monthProp }: CalendarViewProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tz = useBrowserTimeZone();
  const interaction = useTodayInteraction();

  const filters = parseFiltersFromSearchParams(searchParams);
  const listExtras = filterStateToListParams(filters);

  const urlMonth = searchParams.get("month") ?? monthProp ?? null;
  const month = useMemo(() => parseMonthParam(urlMonth), [urlMonth]);

  const urlDate = searchParams.get("date");
  const selectedDate = useMemo(() => parseDateParam(urlDate), [urlDate]);

  const gridCells = useMemo(() => buildMonthGrid(month), [month]);
  const gridStart = gridCells[0];
  const gridEnd = gridCells[gridCells.length - 1];
  const startIso = useMemo(() => toIsoDay(gridStart), [gridStart]);
  const endIso = useMemo(() => toIsoDay(gridEnd), [gridEnd]);

  const entriesQuery = useTodayEntries({
    start: startIso,
    end: endIso,
    tz,
    limit: 2000,
    include_artifacts: true,
    ...listExtras,
  });

  const entries = useMemo<DailyEntryItem[]>(
    () => entriesQuery.data?.entries ?? [],
    [entriesQuery.data],
  );

  const dayMap = useMemo(() => {
    const map = new Map<string, DailyEntryItem[]>();
    for (const entry of entries) {
      const list = map.get(entry.entry_date);
      if (list) list.push(entry);
      else map.set(entry.entry_date, [entry]);
    }
    return map;
  }, [entries]);

  const total = entriesQuery.data?.total ?? 0;
  const truncated = total > entries.length;

  const writeSearchParams = useCallback(
    (mutate: (params: URLSearchParams) => void) => {
      const next = new URLSearchParams(searchParams.toString());
      mutate(next);
      const qs = next.toString();
      router.replace(qs ? `/today?${qs}` : "/today");
    },
    [router, searchParams],
  );

  const setMonthParam = useCallback(
    (next: Date) => {
      writeSearchParams((params) => {
        params.set("month", formatMonthParam(next));
      });
    },
    [writeSearchParams],
  );

  const setSelectedDate = useCallback(
    (next: Date | null) => {
      writeSearchParams((params) => {
        if (next) {
          params.set("date", toIsoDay(next));
        } else {
          params.delete("date");
        }
      });
    },
    [writeSearchParams],
  );

  const onPrevMonth = useCallback(() => {
    setMonthParam(subMonths(month, 1));
  }, [month, setMonthParam]);

  const onNextMonth = useCallback(() => {
    setMonthParam(addMonths(month, 1));
  }, [month, setMonthParam]);

  const onJumpToToday = useCallback(() => {
    const today = new Date();
    writeSearchParams((params) => {
      params.set("month", format(today, "yyyy-MM"));
      params.set("date", toIsoDay(today));
    });
  }, [writeSearchParams]);

  const onSelectDay = useCallback(
    (day: Date) => {
      if (!isSameMonth(day, month)) {
        writeSearchParams((params) => {
          params.set("month", formatMonthParam(day));
          params.set("date", toIsoDay(day));
        });
      } else {
        setSelectedDate(day);
      }
    },
    [month, setSelectedDate, writeSearchParams],
  );

  const onClearSelected = useCallback(() => {
    setSelectedDate(null);
  }, [setSelectedDate]);

  // Keyboard navigation on the calendar surface.
  useEffect(() => {
    function onKey(e: globalThis.KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }

      if (e.key === "Escape" && selectedDate) {
        e.preventDefault();
        onClearSelected();
        return;
      }

      if (!selectedDate) return;

      let delta = 0;
      if (e.key === "ArrowLeft") delta = -1;
      else if (e.key === "ArrowRight") delta = 1;
      else if (e.key === "ArrowUp") delta = -7;
      else if (e.key === "ArrowDown") delta = 7;

      if (delta !== 0) {
        e.preventDefault();
        const next = addDays(selectedDate, delta);
        if (!isSameMonth(next, month)) {
          writeSearchParams((params) => {
            params.set("month", formatMonthParam(next));
            params.set("date", toIsoDay(next));
          });
        } else {
          setSelectedDate(next);
        }
        return;
      }

      if (e.key === "Enter") {
        e.preventDefault();
        interaction.openCreate();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedDate, month, setSelectedDate, onClearSelected, writeSearchParams, interaction]);

  const isLoading = entriesQuery.isLoading;
  const hasError = entriesQuery.isError;
  const monthTitle = format(month, "MMMM yyyy");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onPrevMonth}
            aria-label="Previous month"
            className="size-8 text-[var(--alfred-text-tertiary)] hover:text-foreground"
          >
            <ChevronLeftIcon className="size-4" />
          </Button>
          <h2
            className="font-serif text-[2.625rem] leading-none text-foreground"
            aria-live="polite"
          >
            {monthTitle}
          </h2>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onNextMonth}
            aria-label="Next month"
            className="size-8 text-[var(--alfred-text-tertiary)] hover:text-foreground"
          >
            <ChevronRightIcon className="size-4" />
          </Button>
        </div>

        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onJumpToToday}
          className="font-mono text-[11px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] hover:text-foreground"
        >
          Today
        </Button>
      </div>

      {hasError && (
        <div className="flex items-center justify-between rounded-sm border border-[var(--alfred-ruled-line)] px-3 py-2">
          <p className="font-mono text-[11px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
            Couldn&rsquo;t load entries.
          </p>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-xs uppercase tracking-widest"
            onClick={() => void entriesQuery.refetch()}
          >
            Retry
          </Button>
        </div>
      )}

      {truncated && !isLoading && (
        <div className="rounded-sm border border-[var(--alfred-ruled-line)] px-3 py-2">
          <p className="font-mono text-[11px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
            Showing {entries.length} of {total} entries &mdash; switch to Table view for the full list.
          </p>
        </div>
      )}

      <div
        className={cn(
          "grid gap-4",
          selectedDate ? "grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px]" : "grid-cols-1",
        )}
      >
        <CalendarGrid
          cells={gridCells}
          month={month}
          selectedDate={selectedDate}
          dayMap={dayMap}
          isLoading={isLoading}
          onSelectDay={onSelectDay}
        />

        {selectedDate && (
          <DayPanel
            date={selectedDate}
            entries={dayMap.get(toIsoDay(selectedDate)) ?? []}
            onClose={onClearSelected}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CalendarGrid
// ---------------------------------------------------------------------------

function CalendarGrid({
  cells,
  month,
  selectedDate,
  dayMap,
  isLoading,
  onSelectDay,
}: {
  cells: Date[];
  month: Date;
  selectedDate: Date | null;
  dayMap: Map<string, DailyEntryItem[]>;
  isLoading: boolean;
  onSelectDay: (day: Date) => void;
}) {
  const monthStart = useMemo(() => startOfMonth(month), [month]);
  const monthEnd = useMemo(() => endOfMonth(month), [month]);

  return (
    <div className="overflow-hidden rounded-md border border-[var(--alfred-ruled-line)]">
      <div
        className="grid grid-cols-7 border-b border-[var(--alfred-ruled-line)]"
        role="row"
      >
        {WEEKDAY_HEADERS.map((label) => (
          <div
            key={label}
            role="columnheader"
            className="px-2 py-2 text-center text-[10px] font-medium uppercase tracking-widest text-[var(--alfred-text-tertiary)]"
          >
            {label}
          </div>
        ))}
      </div>

      <div
        className="grid grid-cols-7"
        role="grid"
        aria-label={`Calendar for ${format(month, "MMMM yyyy")}`}
      >
        {isLoading
          ? Array.from({ length: 42 }).map((_, i) => (
              <SkeletonCell
                key={i}
                isLastRow={i >= 35}
                isLastCol={(i + 1) % 7 === 0}
              />
            ))
          : cells.map((day, i) => {
              const iso = toIsoDay(day);
              const dayEntries = dayMap.get(iso) ?? [];
              const isSelected =
                selectedDate !== null && isSameDay(day, selectedDate);
              const inMonth = isSameMonth(day, month);
              return (
                <CalendarDayCell
                  key={iso}
                  day={day}
                  isInMonth={inMonth}
                  isTodayCell={isToday(day)}
                  isSelected={isSelected}
                  entries={dayEntries}
                  onSelect={onSelectDay}
                  isLastRow={i >= 35}
                  isLastCol={(i + 1) % 7 === 0}
                />
              );
            })}
      </div>

      <span className="sr-only">
        Month spans {format(monthStart, "MMMM d, yyyy")} through {format(monthEnd, "MMMM d, yyyy")}.
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CalendarDayCell
// ---------------------------------------------------------------------------

function CalendarDayCell({
  day,
  isInMonth,
  isTodayCell,
  isSelected,
  entries,
  onSelect,
  isLastRow,
  isLastCol,
}: {
  day: Date;
  isInMonth: boolean;
  isTodayCell: boolean;
  isSelected: boolean;
  entries: DailyEntryItem[];
  onSelect: (day: Date) => void;
  isLastRow: boolean;
  isLastCol: boolean;
}) {
  const count = entries.length;
  const hasEntries = count > 0;

  const kindsPresent = useMemo(() => {
    const present = new Set<TodayEntryKind>();
    for (const e of entries) present.add(e.kind);
    return KIND_ORDER.filter((k) => present.has(k));
  }, [entries]);

  const onClick = useCallback(() => onSelect(day), [day, onSelect]);
  const onKey = useCallback(
    (e: ReactKeyboardEvent<HTMLButtonElement>) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onSelect(day);
      }
    },
    [day, onSelect],
  );

  const dayNum = format(day, "d");
  const srLabel = `${format(day, "EEEE, MMMM d, yyyy")}${
    hasEntries
      ? `, ${count} ${count === 1 ? "entry" : "entries"}`
      : ", no entries"
  }${isTodayCell ? ", today" : ""}${isSelected ? ", selected" : ""}`;

  return (
    <button
      type="button"
      role="gridcell"
      onClick={onClick}
      onKeyDown={onKey}
      aria-label={srLabel}
      aria-selected={isSelected || undefined}
      aria-current={isTodayCell ? "date" : undefined}
      tabIndex={isSelected ? 0 : -1}
      className={cn(
        "relative flex min-h-[100px] flex-col items-stretch p-2 text-left",
        "transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-[var(--alfred-accent-muted)]",
        !isLastCol && "border-r border-[var(--alfred-ruled-line)]",
        !isLastRow && "border-b border-[var(--alfred-ruled-line)]",
        // Hover — lighter than selected (accent-subtle at ~50%).
        "hover:bg-[color-mix(in_oklab,var(--alfred-accent-subtle),transparent_50%)]",
        // Selected — full accent-subtle surface.
        isSelected && "bg-[var(--alfred-accent-subtle)]",
        // Today — accent border (inset so neighbor borders are preserved).
        isTodayCell && "ring-2 ring-inset ring-primary",
      )}
    >
      <div className="flex items-start justify-between">
        <span
          className={cn(
            "font-mono text-sm leading-none tabular-nums",
            !isInMonth && "opacity-40",
            // Accent on day number: ONLY for today and selected.
            isTodayCell && "text-primary",
            !isTodayCell && isSelected && "text-primary",
            !isTodayCell && !isSelected && "text-foreground",
          )}
        >
          {dayNum}
        </span>
      </div>

      {hasEntries && isInMonth && kindsPresent.length > 0 && (
        <div
          className="mt-auto flex items-center justify-center gap-1 pb-1 font-mono text-xs text-[var(--alfred-text-tertiary)]"
          aria-hidden="true"
        >
          {kindsPresent.map((k) => (
            <span key={k} title={KIND_LABEL[k]} className="leading-none">
              {KIND_GLYPH[k]}
            </span>
          ))}
        </div>
      )}

      {hasEntries && isInMonth && (
        <span
          className="absolute bottom-1.5 right-2 font-mono text-[10px] tabular-nums text-[var(--alfred-text-tertiary)]"
          aria-hidden="true"
        >
          {count}
        </span>
      )}
    </button>
  );
}

function SkeletonCell({
  isLastRow,
  isLastCol,
}: {
  isLastRow: boolean;
  isLastCol: boolean;
}) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "min-h-[100px] p-2",
        !isLastCol && "border-r border-[var(--alfred-ruled-line)]",
        !isLastRow && "border-b border-[var(--alfred-ruled-line)]",
      )}
    >
      <Skeleton className="h-3 w-5 rounded-sm" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// DayPanel
// ---------------------------------------------------------------------------

function DayPanel({
  date,
  entries,
  onClose,
}: {
  date: Date;
  entries: DailyEntryItem[];
  onClose: () => void;
}) {
  const interaction = useTodayInteraction();

  const weekday = format(date, "EEEE").toUpperCase();
  const longDate = format(date, "MMM d").toUpperCase();
  const relative = (() => {
    const diff = differenceInCalendarDays(date, new Date());
    if (diff === 0) return "TODAY";
    if (diff === -1) return "YESTERDAY";
    if (diff === 1) return "TOMORROW";
    if (diff < 0) return `${-diff}D AGO`;
    return `IN ${diff}D`;
  })();

  const sortedEntries = useMemo(() => {
    const copy = [...entries];
    copy.sort((a, b) => {
      if (a.is_synthetic !== b.is_synthetic) return a.is_synthetic ? 1 : -1;
      const ta = a.updated_at ?? a.created_at ?? "";
      const tb = b.updated_at ?? b.created_at ?? "";
      if (ta === tb) return 0;
      return ta < tb ? 1 : -1;
    });
    return copy;
  }, [entries]);

  const onOpenEntry = useCallback(
    (entry: DailyEntryItem) => {
      if (entry.is_synthetic || typeof entry.id !== "number") return;
      interaction.openEntry(entry.id);
    },
    [interaction],
  );

  const onAddEntry = useCallback(() => {
    interaction.openCreate();
  }, [interaction]);

  return (
    <aside
      className="rounded-md border border-[var(--alfred-ruled-line)] bg-card"
      aria-label={`Entries for ${format(date, "EEEE, MMMM d")}`}
    >
      <div className="flex items-start justify-between border-b border-[var(--alfred-ruled-line)] px-4 py-3">
        <div className="space-y-1">
          <p className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
            {relative}
          </p>
          <p className="font-mono text-xs uppercase tracking-widest text-foreground">
            {weekday} &middot; {longDate}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close day panel"
          className="font-mono text-[11px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] hover:text-foreground"
        >
          Close
        </button>
      </div>

      <div className="max-h-[560px] overflow-y-auto">
        {sortedEntries.length === 0 ? (
          <div className="px-4 py-10 text-center">
            <p className="font-serif text-lg text-foreground">Nothing on this day.</p>
            <p className="mt-1 text-sm text-[var(--alfred-text-tertiary)]">
              Press{" "}
              <kbd className="mx-0.5 inline-flex items-center rounded-sm border border-[var(--alfred-ruled-line)] px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest">
                &#8984;K
              </kbd>{" "}
              or click + to add one.
            </p>
          </div>
        ) : (
          <ul>
            {sortedEntries.map((entry) => (
              <DayPanelRow
                key={String(entry.id)}
                entry={entry}
                onOpen={onOpenEntry}
              />
            ))}
          </ul>
        )}
      </div>

      <div className="border-t border-[var(--alfred-ruled-line)] px-3 py-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onAddEntry}
          className="w-full justify-start font-mono text-[11px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] hover:text-foreground"
        >
          <PlusIcon className="mr-2 size-3.5" />
          Add entry
        </Button>
      </div>
    </aside>
  );
}

function DayPanelRow({
  entry,
  onOpen,
}: {
  entry: DailyEntryItem;
  onOpen: (entry: DailyEntryItem) => void;
}) {
  const isTaskBacked = entry.kind === "todo" && entry.meta?.ref_kind === "task";
  const isArtifact = (entry.is_synthetic || entry.kind === "artifact_ref") && !isTaskBacked;
  const status = entry.status ?? "";
  const kindLabel = isTaskBacked ? "TASK" : entry.kind === "artifact_ref" ? "REF" : entry.kind.toUpperCase();

  const onClick = useCallback(() => onOpen(entry), [entry, onOpen]);
  const onKey = useCallback(
    (e: ReactKeyboardEvent<HTMLLIElement>) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onOpen(entry);
      }
    },
    [entry, onOpen],
  );

  return (
    <li
      role={isArtifact ? undefined : "button"}
      tabIndex={isArtifact ? -1 : 0}
      onClick={isArtifact ? undefined : onClick}
      onKeyDown={isArtifact ? undefined : onKey}
      className={cn(
        "flex items-start gap-2 border-b border-[var(--alfred-ruled-line)] px-4 py-2.5 last:border-b-0",
        !isArtifact &&
          "cursor-pointer transition-colors hover:bg-[var(--alfred-accent-subtle)]",
      )}
    >
      <span className="mt-0.5 w-14 shrink-0 font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
        {kindLabel}
      </span>
      <span
        className={cn(
          "min-w-0 flex-1 truncate text-sm text-foreground",
          status === "done" && "line-through text-[var(--alfred-text-tertiary)]",
          status === "skipped" && "italic text-[var(--alfred-text-tertiary)]",
        )}
      >
        {entry.title || "Untitled"}
      </span>
      {entry.priority >= 3 && (
        <span
          className="font-mono text-xs tabular-nums text-[var(--alfred-text-tertiary)]"
          aria-label={`Priority ${entry.priority}`}
        >
          &middot;&middot;&middot;
        </span>
      )}
    </li>
  );
}
