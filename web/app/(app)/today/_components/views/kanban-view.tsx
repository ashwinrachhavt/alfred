"use client";

/**
 * COLOR BUDGET — Kanban View (Midnight Editorial)
 *
 * Accent #E8590C (bg-primary / text-primary / border-primary) appears ONLY:
 *   1. Today's column header — text-primary on day-name + border-b-2 border-primary
 *   2. Drag overlay ghost — border-l-2 border-primary on the dragging card
 *   (Priority=3 dot uses accent as established in table-view, Color Budget surface #2.)
 *
 * Status and kind expressed via typography (opacity, italic, mono prefixes),
 * NOT semantic colors. All grays via --alfred-* vars.
 */

import { useCallback, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  addDays,
  addWeeks,
  format,
  isValid,
  parseISO,
  startOfWeek,
  subWeeks,
} from "date-fns";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
  type DropAnimation,
} from "@dnd-kit/core";
import { toast } from "sonner";

import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

import {
  filterStateToListParams,
  parseFiltersFromSearchParams,
} from "../filter-state";
import { useUpdateTodayEntry } from "@/features/today/mutations";
import { useTodayEntries, toIsoDay } from "@/features/today/queries";
import { useBrowserTimeZone } from "@/lib/hooks/use-browser-timezone";
import { useTodayInteraction } from "../today-interaction-context";
import type { DailyEntryItem } from "@/features/today/types";

// ---------------------------------------------------------------------------
// Spring easing (from DESIGN.md §Motion — `spring` token, line ~133)
// ---------------------------------------------------------------------------

const SPRING_EASING = "cubic-bezier(0.34, 1.56, 0.64, 1)";

const DROP_ANIMATION: DropAnimation = {
  duration: 300,
  easing: SPRING_EASING,
};

// ---------------------------------------------------------------------------
// Date helpers (ISO week — Monday start)
// ---------------------------------------------------------------------------

function parseWeekParam(week: string | null | undefined): Date {
  if (week) {
    const d = parseISO(week);
    if (isValid(d)) return d;
  }
  return new Date();
}

function getWeekStart(ref: Date): Date {
  // `weekStartsOn: 1` = Monday (ISO week).
  return startOfWeek(ref, { weekStartsOn: 1 });
}

function getWeekDays(weekStart: Date): Date[] {
  return Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
}

function formatWeekLabel(weekStart: Date): string {
  const end = addDays(weekStart, 6);
  const sameYear = weekStart.getFullYear() === end.getFullYear();
  if (sameYear) {
    return `${format(weekStart, "MMM d")} – ${format(end, "MMM d, yyyy")}`;
  }
  return `${format(weekStart, "MMM d, yyyy")} – ${format(end, "MMM d, yyyy")}`;
}

// ---------------------------------------------------------------------------
// Display helpers (mirrors table-view.tsx patterns)
// ---------------------------------------------------------------------------

function priorityDots(priority: number): string {
  if (priority <= 0) return "";
  if (priority === 1) return "·";
  if (priority === 2) return "··";
  return "···";
}

function artifactPrefix(entry: DailyEntryItem): string | null {
  if (entry.kind === "todo" && entry.meta?.ref_kind === "task") return "[TASK]";
  if (entry.kind !== "artifact_ref") return null;
  const source =
    typeof entry.meta?.source === "string"
      ? (entry.meta.source as string).toUpperCase()
      : "";
  if (source) return `[${source}]`;
  const id = String(entry.id);
  if (id.startsWith("zettel:")) return "[ZETTEL]";
  if (id.startsWith("capture:")) return "[CAPTURE]";
  if (id.startsWith("review:")) return "[REVIEW]";
  return "[REF]";
}

function isEditableEntry(entry: DailyEntryItem): entry is DailyEntryItem & { id: number } {
  if (entry.kind === "todo" && entry.meta?.ref_kind === "task") return false;
  return !entry.is_synthetic && typeof entry.id === "number";
}

function sortWithinDay(a: DailyEntryItem, b: DailyEntryItem): number {
  if (a.is_synthetic !== b.is_synthetic) return a.is_synthetic ? 1 : -1;
  const pa = a.priority ?? 0;
  const pb = b.priority ?? 0;
  if (pa !== pb) return pb - pa; // higher priority first
  const ta = a.updated_at ?? a.created_at ?? "";
  const tb = b.updated_at ?? b.created_at ?? "";
  if (ta === tb) return 0;
  return ta < tb ? 1 : -1;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface KanbanViewProps {
  week?: string;
}

export function KanbanView({ week }: KanbanViewProps) {
  const tz = useBrowserTimeZone();
  const router = useRouter();
  const searchParams = useSearchParams();
  const filters = parseFiltersFromSearchParams(searchParams);
  const listExtras = filterStateToListParams(filters);

  const today = useMemo(() => toIsoDay(new Date()), []);
  const weekStart = useMemo(() => getWeekStart(parseWeekParam(week)), [week]);
  const weekDays = useMemo(() => getWeekDays(weekStart), [weekStart]);
  const start = useMemo(() => toIsoDay(weekStart), [weekStart]);
  const end = useMemo(() => toIsoDay(addDays(weekStart, 6)), [weekStart]);

  const entriesQuery = useTodayEntries({
    start,
    end,
    tz,
    include_artifacts: true,
    limit: 500,
    ...listExtras,
  });

  const entries = useMemo<DailyEntryItem[]>(
    () => entriesQuery.data?.entries ?? [],
    [entriesQuery.data],
  );

  // Group by entry_date -> items (sorted within day).
  const weekMap = useMemo<Record<string, DailyEntryItem[]>>(() => {
    const map: Record<string, DailyEntryItem[]> = {};
    for (const d of weekDays) map[toIsoDay(d)] = [];
    for (const e of entries) {
      if (e.entry_date in map) map[e.entry_date].push(e);
    }
    for (const k of Object.keys(map)) map[k].sort(sortWithinDay);
    return map;
  }, [entries, weekDays]);

  const interaction = useTodayInteraction();
  const updateMutation = useUpdateTodayEntry();

  // -----------------------------------------------------------------------
  // Week navigation (reflected in ?week=YYYY-MM-DD).
  // -----------------------------------------------------------------------
  const pushWeek = useCallback(
    (nextStart: Date) => {
      const next = new URLSearchParams(searchParams?.toString() ?? "");
      next.set("view", "kanban");
      next.set("week", toIsoDay(nextStart));
      router.push(`/today?${next.toString()}`);
    },
    [router, searchParams],
  );

  const goPrev = useCallback(
    () => pushWeek(subWeeks(weekStart, 1)),
    [pushWeek, weekStart],
  );
  const goNext = useCallback(
    () => pushWeek(addWeeks(weekStart, 1)),
    [pushWeek, weekStart],
  );
  const goThisWeek = useCallback(
    () => pushWeek(getWeekStart(new Date())),
    [pushWeek],
  );

  // -----------------------------------------------------------------------
  // Drag-and-drop.
  // -----------------------------------------------------------------------
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor),
  );

  const [activeId, setActiveId] = useState<number | null>(null);
  const activeEntry = useMemo(
    () =>
      activeId === null
        ? null
        : entries.find(
            (e) => isEditableEntry(e) && (e.id as number) === activeId,
          ) ?? null,
    [activeId, entries],
  );
  const [overColumn, setOverColumn] = useState<string | null>(null);

  const onDragStart = useCallback((event: DragStartEvent) => {
    const raw = event.active.id;
    if (typeof raw === "number") setActiveId(raw);
  }, []);

  const onDragEnd = useCallback(
    (event: DragEndEvent) => {
      const draggedId = event.active.id;
      const targetDate =
        typeof event.over?.id === "string" ? event.over.id : null;

      setActiveId(null);
      setOverColumn(null);

      if (typeof draggedId !== "number" || !targetDate) return;
      const source = entries.find(
        (e) => isEditableEntry(e) && (e.id as number) === draggedId,
      );
      if (!source) return;
      if (source.entry_date === targetDate) return; // no-op

      updateMutation.mutate(
        { id: draggedId, patch: { entry_date: targetDate } },
        {
          onError: () => {
            toast.error("Couldn't reschedule — try again");
          },
        },
      );
    },
    [entries, updateMutation],
  );

  const onDragCancel = useCallback(() => {
    setActiveId(null);
    setOverColumn(null);
  }, []);

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  const isLoading = entriesQuery.isLoading;
  const hasError = entriesQuery.isError;

  if (hasError) {
    return (
      <div className="rounded-md border border-[var(--alfred-ruled-line)] p-6 text-center">
        <p className="font-serif text-lg text-foreground">
          Couldn&rsquo;t load week.
        </p>
        <p className="mt-1 text-sm text-[var(--alfred-text-tertiary)]">
          {entriesQuery.error instanceof Error
            ? entriesQuery.error.message
            : "Try again in a moment."}
        </p>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="mt-3 text-xs uppercase tracking-widest"
          onClick={() => void entriesQuery.refetch()}
        >
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Week navigation bar */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="font-mono text-[11px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] hover:text-foreground"
            onClick={goPrev}
            aria-label="Previous week"
          >
            ← Prev
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="font-mono text-[11px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] hover:text-foreground"
            onClick={goNext}
            aria-label="Next week"
          >
            Next →
          </Button>
          <button
            type="button"
            onClick={goThisWeek}
            className="ml-1 font-mono text-[11px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] transition-colors hover:text-foreground"
          >
            This Week
          </button>
        </div>
        <p className="font-serif text-base text-foreground">
          {formatWeekLabel(weekStart)}
        </p>
      </div>

      {/* Board */}
      <DndContext
        sensors={sensors}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        onDragCancel={onDragCancel}
        onDragOver={(event) => {
          setOverColumn(
            typeof event.over?.id === "string" ? event.over.id : null,
          );
        }}
      >
        <div
          className="overflow-x-auto"
          role="region"
          aria-label="Weekly swimlanes"
        >
          <div className="flex min-w-full gap-3 pb-2">
            {weekDays.map((d) => {
              const iso = toIsoDay(d);
              const items = weekMap[iso] ?? [];
              const isToday = iso === today;
              return (
                <KanbanColumn
                  key={iso}
                  date={d}
                  iso={iso}
                  items={items}
                  isToday={isToday}
                  isOver={overColumn === iso}
                  isLoading={isLoading}
                  activeId={activeId}
                  onOpenEntry={(entry) => {
                    if (isEditableEntry(entry)) {
                      interaction.openEntry(entry.id);
                    }
                  }}
                  onAddClick={() => interaction.openCreate()}
                />
              );
            })}
          </div>
        </div>

        <DragOverlay dropAnimation={DROP_ANIMATION}>
          {activeEntry ? <KanbanCard entry={activeEntry} overlay /> : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

interface KanbanColumnProps {
  date: Date;
  iso: string;
  items: DailyEntryItem[];
  isToday: boolean;
  isOver: boolean;
  isLoading: boolean;
  activeId: number | null;
  onOpenEntry: (entry: DailyEntryItem) => void;
  onAddClick: () => void;
}

function KanbanColumn({
  date,
  iso,
  items,
  isToday,
  isOver,
  isLoading,
  activeId,
  onOpenEntry,
  onAddClick,
}: KanbanColumnProps) {
  const { setNodeRef } = useDroppable({ id: iso });

  const dayName = format(date, "EEE"); // Mon, Tue, ...
  const dateLabel = format(date, "MMM d"); // Apr 27

  return (
    <div className="flex w-60 min-w-[240px] shrink-0 flex-col">
      {/* Sticky column header */}
      <div
        className={cn(
          "sticky top-0 z-10 bg-background pb-2 pt-1",
          isToday
            ? "border-b-2 border-primary"
            : "border-b border-[var(--alfred-ruled-line)]",
        )}
      >
        <p
          className={cn(
            "text-[11px] font-medium uppercase tracking-widest",
            isToday ? "text-primary" : "text-foreground",
          )}
        >
          {dayName}
        </p>
        <p className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
          {dateLabel}
        </p>
      </div>

      {/* Column body / drop target */}
      <div
        ref={setNodeRef}
        className={cn(
          "mt-2 flex min-h-[12rem] flex-1 flex-col gap-2 rounded-md p-1 transition-colors",
          isOver && "bg-[var(--alfred-accent-subtle)]/50",
        )}
      >
        {isLoading
          ? Array.from({ length: 3 }).map((_, i) => (
              <Skeleton
                key={i}
                className="h-[4.5rem] w-full rounded-md"
                aria-hidden="true"
              />
            ))
          : items.length === 0
            ? (
                <p className="px-2 py-3 text-[12px] text-[var(--alfred-text-tertiary)]">
                  no entries
                </p>
              )
            : items.map((entry) => (
                <DraggableOrStaticCard
                  key={String(entry.id)}
                  entry={entry}
                  isDragging={
                    isEditableEntry(entry) &&
                    activeId !== null &&
                    (entry.id as number) === activeId
                  }
                  onOpen={() => onOpenEntry(entry)}
                />
              ))}

        {/* Column footer: + Add */}
        <button
          type="button"
          onClick={onAddClick}
          className={cn(
            "mt-auto flex items-center gap-1 rounded-sm px-2 py-1.5 text-left",
            "font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]",
            "transition-colors hover:text-foreground",
          )}
          aria-label={`Add entry on ${format(date, "MMM d")}`}
        >
          <span aria-hidden="true">+</span>
          <span>Add</span>
        </button>
      </div>
    </div>
  );
}

function DraggableOrStaticCard({
  entry,
  isDragging,
  onOpen,
}: {
  entry: DailyEntryItem;
  isDragging: boolean;
  onOpen: () => void;
}) {
  if (!isEditableEntry(entry)) {
    // Read-only artifact card — no drag.
    return (
      <button
        type="button"
        onClick={onOpen}
        className="block w-full text-left outline-none"
      >
        <KanbanCard entry={entry} />
      </button>
    );
  }
  return (
    <DraggableCard entry={entry} isDragging={isDragging} onOpen={onOpen} />
  );
}

function DraggableCard({
  entry,
  isDragging,
  onOpen,
}: {
  entry: DailyEntryItem & { id: number };
  isDragging: boolean;
  onOpen: () => void;
}) {
  const { attributes, listeners, setNodeRef } = useDraggable({
    id: entry.id,
  });

  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      onClick={(e) => {
        // Treat clicks (non-drag) as opening the drawer.
        // dnd-kit's PointerSensor only starts dragging after 8px movement,
        // so a simple click falls through to this handler.
        e.stopPropagation();
        onOpen();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          onOpen();
        }
      }}
      className="outline-none"
    >
      <KanbanCard entry={entry} dimmed={isDragging} draggable />
    </div>
  );
}

interface KanbanCardProps {
  entry: DailyEntryItem;
  dimmed?: boolean;
  draggable?: boolean;
  overlay?: boolean;
}

function KanbanCard({
  entry,
  dimmed,
  draggable,
  overlay,
}: KanbanCardProps) {
  const editable = isEditableEntry(entry);
  const prefix = artifactPrefix(entry);
  const isDone = entry.status === "done";
  const dots = priorityDots(entry.priority);

  return (
    <div
      className={cn(
        "rounded-md border border-[var(--alfred-ruled-line)] bg-card p-3",
        "transition-colors hover:border-[var(--alfred-ruled-line)]/60",
        draggable ? "cursor-grab active:cursor-grabbing" : "cursor-default",
        !editable && "opacity-70",
        dimmed && "opacity-50",
        overlay && "border-l-2 border-l-primary shadow-md",
      )}
    >
      {/* Priority dots row (always reserved) */}
      <div
        className={cn(
          "mb-1 font-mono text-xs leading-none tabular-nums",
          entry.priority >= 3
            ? "text-primary"
            : "text-[var(--alfred-text-tertiary)]",
        )}
        aria-label={`Priority ${entry.priority}`}
      >
        {dots || " "}
      </div>

      {/* Title */}
      <p
        className={cn(
          "text-[14px] font-medium leading-snug text-foreground",
          // DM Sans is the body/UI font — no serif override needed.
          isDone && "line-through text-[var(--alfred-text-tertiary)]",
        )}
      >
        {prefix && (
          <span className="mr-1 font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
            {prefix}
          </span>
        )}
        {entry.title || "Untitled"}
      </p>

      {/* Meta row: kind + tags */}
      <div className="mt-2 flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
        <span>{entry.kind === "artifact_ref" ? "REF" : entry.kind}</span>
        {entry.tags.length > 0 && (
          <>
            <span aria-hidden="true">·</span>
            <span className="truncate normal-case tracking-normal">
              {entry.tags.join(", ")}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
