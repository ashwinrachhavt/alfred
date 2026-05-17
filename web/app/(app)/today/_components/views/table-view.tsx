"use client";

/**
 * COLOR BUDGET — Today Page (Midnight Editorial)
 *
 * Accent color #E8590C (via bg-primary / text-primary / border-primary) is
 * limited to these surfaces only:
 *   1. Active view toggle in TodayHeader
 *   2. Priority=3 row indicator
 *   3. Save / Create CTA in EntryDrawer
 *   4. Selected-row left border when drawer is open for that id
 *
 * Everywhere else: warm monochrome via --alfred-* vars. Status expressed via
 * typography (strikethrough, opacity, italic), NOT semantic colors.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
} from "react";
import { useSearchParams } from "next/navigation";
import { addDays, format, parseISO, subDays } from "date-fns";
import {
  CheckIcon,
  CircleDashedIcon,
  CircleDotIcon,
  FileTextIcon,
  LinkIcon,
  MoreHorizontalIcon,
  PlusIcon,
  XIcon,
} from "lucide-react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

import {
  filterStateToListParams,
  parseFiltersFromSearchParams,
} from "../filter-state";
import {
  useCreateTodayEntry,
  useDeleteTodayEntry,
  useUpdateTodayEntry,
} from "@/features/today/mutations";
import { useTodayEntries, toIsoDay } from "@/features/today/queries";
import { useBrowserTimeZone } from "@/lib/hooks/use-browser-timezone";
import { useTodayInteraction } from "../today-interaction-context";
import type {
  DailyEntryItem,
  TodayEntryStatus,
} from "@/features/today/types";

const STATUS_CYCLE: TodayEntryStatus[] = ["open", "doing", "done", "skipped"];

const COL_WIDTHS = {
  status: "w-8",
  title: "",
  kind: "w-24",
  tags: "w-40",
  priority: "w-12",
  date: "w-20",
} as const;

function nextStatus(current: string | null | undefined): TodayEntryStatus {
  if (!current) return "doing";
  const idx = STATUS_CYCLE.indexOf(current as TodayEntryStatus);
  if (idx < 0) return "doing";
  return STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];
}

function priorityDots(priority: number): string {
  if (priority <= 0) return "";
  if (priority === 1) return "·";
  if (priority === 2) return "··";
  return "···";
}

function groupByDay(entries: DailyEntryItem[]): { date: string; items: DailyEntryItem[] }[] {
  const buckets = new Map<string, DailyEntryItem[]>();
  for (const e of entries) {
    const list = buckets.get(e.entry_date);
    if (list) list.push(e);
    else buckets.set(e.entry_date, [e]);
  }
  // Sort buckets by date descending.
  const sortedDates = Array.from(buckets.keys()).sort((a, b) => (a < b ? 1 : -1));
  return sortedDates.map((date) => {
    const items = buckets.get(date) ?? [];
    // Sort within a day: non-synthetic first, then by updated_at/created_at desc.
    items.sort((a, b) => {
      if (a.is_synthetic !== b.is_synthetic) return a.is_synthetic ? 1 : -1;
      const ta = a.updated_at ?? a.created_at ?? "";
      const tb = b.updated_at ?? b.created_at ?? "";
      if (ta === tb) return 0;
      return ta < tb ? 1 : -1;
    });
    return { date, items };
  });
}

function formatDayHeader(iso: string): string {
  try {
    const d = parseISO(iso);
    return format(d, "EEEE, MMMM d");
  } catch {
    return iso;
  }
}

function formatDateCell(iso: string): string {
  try {
    return format(parseISO(iso), "MMM dd");
  } catch {
    return iso;
  }
}

function artifactPrefix(entry: DailyEntryItem): string | null {
  if (entry.kind !== "artifact_ref") return null;
  const source =
    typeof entry.meta?.source === "string" ? (entry.meta.source as string).toUpperCase() : "";
  if (source) return `[${source}]`;
  // Fallback: infer from the synthetic id prefix.
  const id = String(entry.id);
  if (id.startsWith("zettel:")) return "[ZETTEL]";
  if (id.startsWith("capture:")) return "[CAPTURE]";
  if (id.startsWith("review:")) return "[REVIEW]";
  return "[REF]";
}

function artifactHref(entry: DailyEntryItem): string | null {
  const meta = entry.meta ?? {};
  const refUrl = typeof meta.ref_url === "string" ? (meta.ref_url as string) : null;
  if (refUrl) return refUrl;
  const id = String(entry.id);
  if (id.startsWith("zettel:")) return `/knowledge/${id.slice("zettel:".length)}`;
  if (id.startsWith("capture:")) return `/documents/${id.slice("capture:".length)}`;
  return null;
}

interface TableViewProps {
  date?: string;
}

export function TableView({ date }: TableViewProps) {
  const tz = useBrowserTimeZone();
  const searchParams = useSearchParams();
  const filters = parseFiltersFromSearchParams(searchParams);
  const listExtras = filterStateToListParams(filters);

  // First-deploy row budget: last 7 days (centered on `date` if provided).
  const { start, end } = useMemo(() => {
    const ref = date ? parseISO(date) : new Date();
    return {
      start: toIsoDay(subDays(ref, 6)),
      end: toIsoDay(addDays(ref, 0)),
    };
  }, [date]);

  const entriesQuery = useTodayEntries({
    start,
    end,
    tz,
    limit: 500,
    ...listExtras,
  });

  const entries = useMemo<DailyEntryItem[]>(
    () => entriesQuery.data?.entries ?? [],
    [entriesQuery.data],
  );
  const grouped = useMemo(() => groupByDay(entries), [entries]);

  const interaction = useTodayInteraction();
  const updateMutation = useUpdateTodayEntry();
  const createMutation = useCreateTodayEntry();
  const deleteMutation = useDeleteTodayEntry();

  // Inline new-entry row state.
  const [newTitle, setNewTitle] = useState("");
  const newRowInputRef = useRef<HTMLInputElement | null>(null);

  const onSubmitNew = useCallback(async () => {
    const title = newTitle.trim();
    if (!title) return;
    try {
      await createMutation.mutateAsync({
        entry_date: toIsoDay(new Date()),
        kind: "todo",
        title,
      });
      setNewTitle("");
      newRowInputRef.current?.focus();
    } catch {
      toast.error("Failed to create entry");
    }
  }, [createMutation, newTitle]);

  const onToggleStatus = useCallback(
    (entry: DailyEntryItem, e?: MouseEvent) => {
      e?.stopPropagation();
      if (entry.is_synthetic || typeof entry.id !== "number") return;
      const next = nextStatus(entry.status);
      updateMutation.mutate({ id: entry.id, patch: { status: next } });
    },
    [updateMutation],
  );

  const onOpenRow = useCallback(
    (entry: DailyEntryItem) => {
      if (entry.is_synthetic || typeof entry.id !== "number") {
        const href = artifactHref(entry);
        if (href) window.open(href, "_blank", "noopener,noreferrer");
        return;
      }
      interaction.openEntry(entry.id);
    },
    [interaction],
  );

  const onDelete = useCallback(
    async (entry: DailyEntryItem) => {
      if (entry.is_synthetic || typeof entry.id !== "number") return;
      if (!window.confirm(`Delete "${entry.title}"? This cannot be undone.`)) return;
      try {
        await deleteMutation.mutateAsync(entry.id);
        toast.success("Entry deleted");
      } catch {
        toast.error("Failed to delete entry");
      }
    },
    [deleteMutation],
  );

  const onDuplicate = useCallback(
    async (entry: DailyEntryItem) => {
      if (entry.is_synthetic || entry.kind === "artifact_ref") return;
      try {
        await createMutation.mutateAsync({
          entry_date: toIsoDay(new Date()),
          kind: entry.kind,
          title: entry.title,
          body_md: entry.body_md,
          priority: entry.priority,
          tags: [...entry.tags],
          status: "open",
        });
        toast.success("Entry duplicated");
      } catch {
        toast.error("Failed to duplicate");
      }
    },
    [createMutation],
  );

  // -----------------------------------------------------------------------
  // Keyboard navigation (j/k/Enter/Space/Esc). Disabled when focus is in an
  // input/textarea/contenteditable.
  // -----------------------------------------------------------------------
  const flatEditable = useMemo(
    () => entries.filter((e) => !e.is_synthetic && typeof e.id === "number"),
    [entries],
  );
  const [activeIdx, setActiveIdx] = useState<number>(-1);
  const activeId = activeIdx >= 0 ? (flatEditable[activeIdx]?.id ?? null) : null;

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
      if (flatEditable.length === 0) return;
      if (e.key === "j") {
        e.preventDefault();
        setActiveIdx((i) => Math.min(flatEditable.length - 1, Math.max(0, i + 1)));
      } else if (e.key === "k") {
        e.preventDefault();
        setActiveIdx((i) => Math.max(0, i - 1));
      } else if (e.key === "Enter" && activeIdx >= 0) {
        e.preventDefault();
        const entry = flatEditable[activeIdx];
        if (entry) onOpenRow(entry);
      } else if (e.key === " " && activeIdx >= 0) {
        e.preventDefault();
        const entry = flatEditable[activeIdx];
        if (entry) onToggleStatus(entry);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [flatEditable, activeIdx, onOpenRow, onToggleStatus]);

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  const isLoading = entriesQuery.isLoading;
  const hasError = entriesQuery.isError;
  const isEmpty =
    !isLoading && !hasError && entries.length === 0 && entriesQuery.isSuccess;
  const nextCursor = entriesQuery.data?.next_cursor ?? null;

  return (
    <div className="space-y-2">
      <table className="w-full border-separate border-spacing-0 text-sm">
        <colgroup>
          <col className={COL_WIDTHS.status} />
          <col />
          <col className={COL_WIDTHS.kind} />
          <col className={COL_WIDTHS.tags} />
          <col className={COL_WIDTHS.priority} />
          <col className={COL_WIDTHS.date} />
        </colgroup>
        <thead>
          <tr>
            <HeaderCell className="pl-3"></HeaderCell>
            <HeaderCell>Title</HeaderCell>
            <HeaderCell>Kind</HeaderCell>
            <HeaderCell>Tags</HeaderCell>
            <HeaderCell className="text-right">Pri</HeaderCell>
            <HeaderCell className="text-right pr-3">Date</HeaderCell>
          </tr>
        </thead>

        <tbody>
          {/* Inline new-entry row — always visible at the top. */}
          <tr className="border-b border-[var(--alfred-ruled-line)]">
            <td className="py-2 pl-3 align-middle">
              <span
                className="inline-flex size-4 items-center justify-center rounded-sm border border-[var(--alfred-ruled-line)] text-[var(--alfred-text-tertiary)]"
                aria-hidden="true"
              >
                <PlusIcon className="size-3" />
              </span>
            </td>
            <td className="py-2 pr-3 align-middle" colSpan={5}>
              <input
                ref={newRowInputRef}
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    void onSubmitNew();
                  } else if (e.key === "Escape") {
                    setNewTitle("");
                  }
                }}
                placeholder="New todo for today — press Enter"
                className="w-full border-0 bg-transparent p-0 text-sm text-foreground placeholder:text-[var(--alfred-text-tertiary)] focus-visible:outline-none"
                aria-label="Quickly add a new todo for today"
                disabled={createMutation.isPending}
              />
            </td>
          </tr>

          {/* Loading skeleton rows */}
          {isLoading && <SkeletonRows />}

          {/* Error row */}
          {hasError && (
            <tr>
              <td colSpan={6} className="px-3 py-6 text-center">
                <p className="font-serif text-lg text-foreground">Couldn&rsquo;t load entries.</p>
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
              </td>
            </tr>
          )}

          {/* Empty state */}
          {isEmpty && <EmptyStateRow />}

          {/* Data rows, grouped by day */}
          {!isLoading && !hasError &&
            grouped.map((group) => (
              <GroupBlock
                key={group.date}
                date={group.date}
                items={group.items}
                activeId={activeId}
                drawerId={
                  typeof interaction.drawerTarget === "number"
                    ? interaction.drawerTarget
                    : null
                }
                onToggleStatus={onToggleStatus}
                onOpenRow={onOpenRow}
                onDelete={onDelete}
                onDuplicate={onDuplicate}
              />
            ))}
        </tbody>
      </table>

      {/* Pagination — manual, not infinite scroll */}
      {nextCursor && !isLoading && (
        <div className="flex justify-center pt-2">
          <Button
            variant="ghost"
            size="sm"
            className="text-xs uppercase tracking-widest"
            onClick={() => toast.message("Load more not wired yet — widen the date range.")}
          >
            Load more
          </Button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function HeaderCell({
  children,
  className,
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <th
      scope="col"
      className={cn(
        "border-b border-[var(--alfred-ruled-line)] px-2 pb-2 pt-1 text-left",
        "text-[10px] font-medium uppercase tracking-widest text-[var(--alfred-text-tertiary)]",
        className,
      )}
    >
      {children}
    </th>
  );
}

function GroupBlock({
  date,
  items,
  activeId,
  drawerId,
  onToggleStatus,
  onOpenRow,
  onDelete,
  onDuplicate,
}: {
  date: string;
  items: DailyEntryItem[];
  activeId: number | string | null;
  drawerId: number | null;
  onToggleStatus: (entry: DailyEntryItem, e?: MouseEvent) => void;
  onOpenRow: (entry: DailyEntryItem) => void;
  onDelete: (entry: DailyEntryItem) => void;
  onDuplicate: (entry: DailyEntryItem) => void;
}) {
  return (
    <>
      <tr>
        <td colSpan={6} className="pb-1 pt-5">
          <p className="font-serif text-base text-foreground">{formatDayHeader(date)}</p>
        </td>
      </tr>
      {items.map((entry) => (
        <EntryRow
          key={String(entry.id)}
          entry={entry}
          isActive={activeId !== null && entry.id === activeId}
          isOpen={drawerId !== null && entry.id === drawerId}
          onToggleStatus={onToggleStatus}
          onOpenRow={onOpenRow}
          onDelete={onDelete}
          onDuplicate={onDuplicate}
        />
      ))}
    </>
  );
}

function EntryRow({
  entry,
  isActive,
  isOpen,
  onToggleStatus,
  onOpenRow,
  onDelete,
  onDuplicate,
}: {
  entry: DailyEntryItem;
  isActive: boolean;
  isOpen: boolean;
  onToggleStatus: (entry: DailyEntryItem, e?: MouseEvent) => void;
  onOpenRow: (entry: DailyEntryItem) => void;
  onDelete: (entry: DailyEntryItem) => void;
  onDuplicate: (entry: DailyEntryItem) => void;
}) {
  const isTaskBacked = entry.kind === "todo" && entry.meta?.ref_kind === "task";
  const isArtifact = (entry.is_synthetic || entry.kind === "artifact_ref") && !isTaskBacked;
  const prefix = isTaskBacked ? "[TASK]" : artifactPrefix(entry);
  const href = artifactHref(entry);

  const rowKey = useCallback(
    (e: KeyboardEvent<HTMLTableRowElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onOpenRow(entry);
      }
    },
    [entry, onOpenRow],
  );

  return (
    <tr
      tabIndex={0}
      onClick={() => onOpenRow(entry)}
      onKeyDown={rowKey}
      className={cn(
        "group cursor-pointer border-b border-[var(--alfred-ruled-line)] transition-colors",
        "hover:bg-[var(--alfred-accent-subtle)]",
        isOpen && "bg-[var(--alfred-accent-subtle)]",
        isActive && "bg-[var(--alfred-accent-subtle)]",
      )}
      aria-selected={isOpen ? "true" : undefined}
    >
      {/* Status toggle */}
      <td
        className={cn(
          "py-2 pl-3 align-middle",
          isOpen && "border-l-2 border-primary",
        )}
      >
        <StatusToggle entry={entry} onToggle={onToggleStatus} />
      </td>

      {/* Title */}
      <td className="py-2 px-2 align-middle">
        <div className="flex items-center gap-2 min-w-0">
          {prefix && (
            <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] shrink-0">
              {prefix}
            </span>
          )}
          <span
            className={cn(
              "truncate text-sm text-foreground",
              entry.status === "done" && "line-through text-[var(--alfred-text-tertiary)]",
            )}
          >
            {entry.title || "Untitled"}
          </span>
        </div>
      </td>

      {/* Kind */}
      <td className="py-2 px-2 align-middle">
        <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
          {isTaskBacked ? "TASK" : entry.kind === "artifact_ref" ? "REF" : entry.kind}
        </span>
      </td>

      {/* Tags */}
      <td className="py-2 px-2 align-middle">
        <span className="truncate font-mono text-[11px] text-[var(--alfred-text-tertiary)]">
          {entry.tags.join(", ")}
        </span>
      </td>

      {/* Priority */}
      <td className="py-2 px-2 text-right align-middle">
        <span
          className={cn(
            "font-mono text-sm tabular-nums",
            entry.priority >= 3 ? "text-primary" : "text-[var(--alfred-text-tertiary)]",
          )}
          aria-label={`Priority ${entry.priority}`}
        >
          {priorityDots(entry.priority)}
        </span>
      </td>

      {/* Date */}
      <td className="py-2 pr-1 align-middle text-right">
        <div
          className="flex items-center justify-end gap-1"
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
          role="presentation"
        >
          <span className="font-mono text-[11px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
            {formatDateCell(entry.entry_date)}
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                onClick={(e) => e.stopPropagation()}
                className="rounded-sm p-1 text-[var(--alfred-text-tertiary)] opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100"
                aria-label="Row actions"
              >
                <MoreHorizontalIcon className="size-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="text-xs">
              {isArtifact ? (
                <DropdownMenuItem
                  onSelect={() => {
                    if (href) window.open(href, "_blank", "noopener,noreferrer");
                  }}
                  disabled={!href}
                >
                  Open source
                </DropdownMenuItem>
              ) : (
                <>
                  <DropdownMenuItem onSelect={() => onOpenRow(entry)}>Edit</DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => void onDuplicate(entry)}>
                    Duplicate
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    variant="destructive"
                    onSelect={() => void onDelete(entry)}
                  >
                    Delete
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </td>
    </tr>
  );
}

function StatusToggle({
  entry,
  onToggle,
}: {
  entry: DailyEntryItem;
  onToggle: (entry: DailyEntryItem, e?: MouseEvent) => void;
}) {
  const isTaskBacked = entry.kind === "todo" && entry.meta?.ref_kind === "task";
  const isArtifact = (entry.is_synthetic || entry.kind === "artifact_ref") && !isTaskBacked;
  if (isArtifact) {
    const id = String(entry.id);
    const Icon = id.startsWith("zettel:")
      ? FileTextIcon
      : id.startsWith("capture:")
        ? LinkIcon
        : CircleDashedIcon;
    return (
      <span
        className="inline-flex size-4 items-center justify-center text-[var(--alfred-text-tertiary)]"
        aria-label="Artifact reference"
      >
        <Icon className="size-3.5" />
      </span>
    );
  }
  const status = entry.status ?? "open";
  const label = status;
  return (
    <button
      type="button"
      onClick={(e) => onToggle(entry, e)}
      className={cn(
        "inline-flex size-4 items-center justify-center rounded-sm border transition-colors",
        // Status is expressed via typography + warm monochrome, NOT accent.
        // Accent (primary) is reserved for the 4 budgeted surfaces above.
        status === "done"
          ? "border-[var(--alfred-text-tertiary)] bg-[var(--alfred-text-tertiary)] text-background"
          : status === "doing"
            ? "border-foreground text-foreground"
            : status === "skipped"
              ? "border-[var(--alfred-ruled-line)] text-[var(--alfred-text-tertiary)]"
              : "border-[var(--alfred-ruled-line)] text-transparent hover:border-[var(--alfred-text-tertiary)]",
      )}
      aria-label={`Status: ${label}. Click to cycle.`}
      title={`Status: ${label}`}
    >
      {status === "done" && <CheckIcon className="size-3" />}
      {status === "doing" && <CircleDotIcon className="size-3" />}
      {status === "skipped" && <XIcon className="size-3" />}
    </button>
  );
}

function EmptyStateRow() {
  return (
    <tr>
      <td colSpan={6} className="px-3 py-16 text-center">
        <p className="font-serif text-2xl text-foreground">Nothing here yet.</p>
        <p className="mt-2 text-sm text-[var(--alfred-text-tertiary)]">
          Press{" "}
          <kbd className="mx-0.5 inline-flex items-center rounded-sm border border-[var(--alfred-ruled-line)] px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest">
            ⌘K
          </kbd>{" "}
          or{" "}
          <kbd className="mx-0.5 inline-flex items-center rounded-sm border border-[var(--alfred-ruled-line)] px-1.5 py-0.5 font-mono text-[10px]">
            +
          </kbd>{" "}
          to add your first entry.
        </p>
      </td>
    </tr>
  );
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <tr
          key={i}
          className="border-b border-[var(--alfred-ruled-line)]"
          aria-hidden="true"
        >
          <td className="py-3 pl-3 align-middle">
            <Skeleton className="size-4 rounded-sm" />
          </td>
          <td className="py-3 px-2 align-middle">
            <Skeleton className="h-3 w-2/3 rounded-sm" />
          </td>
          <td className="py-3 px-2 align-middle">
            <Skeleton className="h-3 w-12 rounded-sm" />
          </td>
          <td className="py-3 px-2 align-middle">
            <Skeleton className="h-3 w-24 rounded-sm" />
          </td>
          <td className="py-3 px-2 align-middle">
            <Skeleton className="ml-auto h-3 w-8 rounded-sm" />
          </td>
          <td className="py-3 pr-3 align-middle">
            <Skeleton className="ml-auto h-3 w-16 rounded-sm" />
          </td>
        </tr>
      ))}
    </>
  );
}
