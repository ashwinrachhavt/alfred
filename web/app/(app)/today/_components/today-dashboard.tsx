"use client";

import Link from "next/link";
import { memo, useCallback, useMemo, useState, type ReactNode } from "react";

import {
  addDays,
  endOfMonth,
  endOfWeek,
  format,
  isSameMonth,
  isToday,
  isYesterday,
  parseISO,
  startOfDay,
  startOfMonth,
  startOfWeek,
} from "date-fns";
import {
  Brain,
  ChevronLeft,
  ChevronRight,
  FileText,
  GitBranch,
  NotebookPen,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { type TodayCalendarDay } from "@/lib/api/today";
import { useBrowserTimeZone } from "@/lib/hooks/use-browser-timezone";
import {
  TODAY_AUDIT_KINDS,
  type TodayAuditEvent,
  type TodayAuditEventKind,
  buildTodayTimeline,
  getBriefingCountForKind,
  getCalendarDayCountForKind,
  getCalendarDayTotalForKinds,
  makeCalendarDayMap,
} from "@/features/today/utils";
import { useTodayBriefing, useTodayCalendar, toIsoDay } from "@/features/today/queries";
import { cn } from "@/lib/utils";

type TodayAuditScope = "day" | "week" | "month";

const AUDIT_KIND_LABELS: Record<TodayAuditEventKind, string> = {
  capture: "Captures",
  stored: "Cards",
  connection: "Links",
  review: "Reviews",
  gap: "Gaps",
};

function formatSelectedDateLabel(value: Date): string {
  if (isToday(value)) return "Today";
  if (isYesterday(value)) return "Yesterday";
  return format(value, "EEEE, MMMM d");
}

function formatTimestamp(value: string | null): string {
  if (!value) return "Untimed";
  try {
    return format(parseISO(value), "h:mm a");
  } catch {
    return "Untimed";
  }
}

function formatCountLabel(value: number, noun: string): string {
  return `${value} ${noun}${value === 1 ? "" : "s"}`;
}

function formatAuditScopeLabel(
  scope: TodayAuditScope,
  selectedDate: Date,
  scopeStart: Date,
  scopeEnd: Date,
): string {
  switch (scope) {
    case "day":
      return format(selectedDate, "MMMM d, yyyy");
    case "week":
      return `${format(scopeStart, "MMM d")} to ${format(scopeEnd, "MMM d, yyyy")}`;
    case "month":
      return format(selectedDate, "MMMM yyyy");
  }
}

function describeCollapsedDay(
  day: TodayCalendarDay,
  selectedKinds: Set<TodayAuditEventKind>,
): string {
  const parts = TODAY_AUDIT_KINDS.flatMap((kind) => {
    if (!selectedKinds.has(kind)) return [];

    const count = getCalendarDayCountForKind(day, kind);
    if (count === 0) return [];

    return `${count} ${AUDIT_KIND_LABELS[kind].toLowerCase()}`;
  });

  if (parts.length > 0) {
    return parts.join(" · ");
  }

  if (day.total_events > 0) {
    return "Activity exists here, but none of it matches the current filters.";
  }

  return "Quiet day";
}

function StatCard({
  icon: Icon,
  label,
  value,
  meta,
}: {
  icon: typeof FileText;
  label: string;
  value: number;
  meta?: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.16em] text-[var(--alfred-text-tertiary)]">
        <Icon className="size-3.5" />
        <span className="font-mono">{label}</span>
      </div>
      <div className="mt-3 flex items-end justify-between gap-3">
        <p className="font-serif text-3xl leading-none tabular-nums">{value}</p>
        {meta ? (
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
            {meta}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function PanelHeader({
  title,
  subtitle,
  count,
}: {
  title: string;
  subtitle?: string;
  count?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--alfred-text-tertiary)]">
          {title}
        </div>
        {subtitle ? <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p> : null}
      </div>
      {count !== undefined ? (
        <span className="rounded-sm border bg-[var(--alfred-accent-subtle)] px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-primary">
          {count}
        </span>
      ) : null}
    </div>
  );
}

function SectionCard({
  title,
  subtitle,
  count,
  children,
}: {
  title: string;
  subtitle?: string;
  count: number;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border bg-card p-5">
      <PanelHeader title={title} subtitle={subtitle} count={count} />
      <div className="mt-4">{children}</div>
    </section>
  );
}

const TimelineItem = memo(function TimelineItem({ event }: { event: TodayAuditEvent }) {
  const kindMeta = {
    capture: { icon: FileText, label: "Captured" },
    stored: { icon: NotebookPen, label: "Stored" },
    connection: { icon: GitBranch, label: "Connected" },
    review: { icon: Brain, label: "Review" },
    gap: { icon: Sparkles, label: "Gap" },
  } as const;

  const meta = kindMeta[event.kind];

  return (
    <div className="grid gap-3 rounded-lg border px-4 py-3 md:grid-cols-[auto_minmax(0,1fr)_auto] md:items-center">
      <div className="flex size-9 items-center justify-center rounded-full bg-[var(--alfred-accent-subtle)] text-primary">
        <meta.icon className="size-4" />
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--alfred-text-tertiary)]">
            {meta.label}
          </span>
          {event.status ? (
            <span className="rounded-sm bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--alfred-text-tertiary)]">
              {event.status}
            </span>
          ) : null}
        </div>
        <Link href={event.href} className="mt-1 block truncate text-sm hover:text-primary">
          {event.title}
        </Link>
        <p className="mt-1 text-xs text-muted-foreground">{event.meta}</p>
      </div>
      <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
        {formatTimestamp(event.timestamp)}
      </div>
    </div>
  );
});

const CollapsedAuditRow = memo(function CollapsedAuditRow({
  day,
  isSelected,
  selectedKinds,
  onSelectDay,
}: {
  day: TodayCalendarDay;
  isSelected: boolean;
  selectedKinds: Set<TodayAuditEventKind>;
  onSelectDay: (isoDate: string) => void;
}) {
  const filteredTotal = getCalendarDayTotalForKinds(day, selectedKinds);

  return (
    <button
      type="button"
      onClick={() => onSelectDay(day.date)}
      className={cn(
        "w-full rounded-lg border px-4 py-3 text-left transition-colors hover:border-[var(--border-strong)] hover:bg-[var(--alfred-accent-subtle)]",
        isSelected && "border-[var(--border-strong)] bg-[var(--alfred-accent-subtle)]",
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium">{format(parseISO(day.date), "EEE, MMM d")}</span>
            {isSelected ? (
              <span className="rounded-sm border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
                selected day
              </span>
            ) : null}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">{describeCollapsedDay(day, selectedKinds)}</p>
        </div>
        <div className="text-right">
          <div className="font-serif text-2xl leading-none tabular-nums">{filteredTotal}</div>
          <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
            {formatCountLabel(filteredTotal, "filtered event")}
          </div>
        </div>
      </div>
    </button>
  );
});

function EmptyPanel({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-xl border border-dashed p-6 text-center">
      <p className="font-serif text-xl">{title}</p>
      <p className="mt-2 text-sm text-muted-foreground">{body}</p>
    </div>
  );
}

export function TodayDashboard() {
  const today = startOfDay(new Date());
  const [selectedDate, setSelectedDate] = useState(today);
  const [visibleMonth, setVisibleMonth] = useState(today);
  const [auditScope, setAuditScope] = useState<TodayAuditScope>("day");
  const [selectedKinds, setSelectedKinds] = useState<TodayAuditEventKind[]>(TODAY_AUDIT_KINDS);
  const timeZone = useBrowserTimeZone();

  const selectDate = useCallback((value: Date) => {
    const normalized = startOfDay(value);
    setSelectedDate(normalized);
    setVisibleMonth(normalized);
  }, []);

  const handleScopeChange = useCallback((value: string) => {
    if (!value) return;
    setAuditScope(value as TodayAuditScope);
  }, []);

  const handleKindsChange = useCallback((value: string[]) => {
    if (value.length === 0) return;
    setSelectedKinds(value as TodayAuditEventKind[]);
  }, []);

  const handleResetKinds = useCallback(() => {
    setSelectedKinds(TODAY_AUDIT_KINDS);
  }, []);

  const handleDrillIntoDay = useCallback(
    (isoDate: string) => {
      setAuditScope("day");
      selectDate(parseISO(isoDate));
    },
    [selectDate],
  );

  const goToPreviousDay = useCallback(() => {
    selectDate(addDays(selectedDate, -1));
  }, [selectDate, selectedDate]);

  const goToNextDay = useCallback(() => {
    const nextDate = addDays(selectedDate, 1);
    if (nextDate > today) return;
    selectDate(nextDate);
  }, [selectDate, selectedDate, today]);

  const goToToday = useCallback(() => {
    selectDate(today);
  }, [selectDate, today]);

  const briefingQuery = useTodayBriefing(selectedDate, timeZone);
  const calendarQuery = useTodayCalendar(visibleMonth, timeZone);

  const activityByDay = useMemo(
    () => makeCalendarDayMap(calendarQuery.data?.days ?? []),
    [calendarQuery.data?.days],
  );

  const selectedDayKey = toIsoDay(selectedDate);
  const selectedDaySummary = activityByDay.get(selectedDayKey);
  const timeline = useMemo(
    () => (briefingQuery.data ? buildTodayTimeline(briefingQuery.data) : []),
    [briefingQuery.data],
  );
  const selectedKindSet = useMemo(
    () => new Set<TodayAuditEventKind>(selectedKinds),
    [selectedKinds],
  );

  const scopeStart = useMemo(() => {
    switch (auditScope) {
      case "day":
        return selectedDate;
      case "week":
        return startOfWeek(selectedDate, { weekStartsOn: 1 });
      case "month":
        return startOfMonth(selectedDate);
    }
  }, [auditScope, selectedDate]);

  const scopeEnd = useMemo(() => {
    switch (auditScope) {
      case "day":
        return selectedDate;
      case "week":
        return endOfWeek(selectedDate, { weekStartsOn: 1 });
      case "month":
        return endOfMonth(selectedDate);
    }
  }, [auditScope, selectedDate]);

  const scopeCalendarDays = useMemo(() => {
    const startKey = toIsoDay(scopeStart);
    const endKey = toIsoDay(scopeEnd);

    return (calendarQuery.data?.days ?? [])
      .filter((day) => day.date >= startKey && day.date <= endKey)
      .sort((left, right) => right.date.localeCompare(left.date));
  }, [calendarQuery.data?.days, scopeEnd, scopeStart]);

  const collapsedAuditDays = useMemo(() => {
    if (auditScope === "day") return [];
    if (auditScope === "week") return scopeCalendarDays;

    return scopeCalendarDays.filter((day) => day.total_events > 0 || day.date === selectedDayKey);
  }, [auditScope, scopeCalendarDays, selectedDayKey]);

  const filteredTimeline = useMemo(
    () => timeline.filter((event) => selectedKindSet.has(event.kind)),
    [selectedKindSet, timeline],
  );

  const monthAuditDays = useMemo(() => {
    return (calendarQuery.data?.days ?? [])
      .filter((day) => day.total_events > 0 && isSameMonth(parseISO(day.date), visibleMonth))
      .sort((left, right) => {
        if (right.total_events !== left.total_events) {
          return right.total_events - left.total_events;
        }
        return left.date.localeCompare(right.date);
      })
      .slice(0, 8);
  }, [calendarQuery.data?.days, visibleMonth]);

  const monthTotals = useMemo(() => {
    return (calendarQuery.data?.days ?? [])
      .filter((day) => isSameMonth(parseISO(day.date), visibleMonth))
      .reduce(
        (acc, day) => {
          acc.captures += day.captures;
          acc.stored_cards += day.stored_cards;
          acc.connections += day.connections;
          acc.reviews_due += day.reviews_due;
          acc.gaps += day.gaps;
          acc.total_events += day.total_events;
          if (day.total_events > 0) acc.active_days += 1;
          return acc;
        },
        {
          captures: 0,
          stored_cards: 0,
          connections: 0,
          reviews_due: 0,
          gaps: 0,
          total_events: 0,
          active_days: 0,
        },
      );
  }, [calendarQuery.data?.days, visibleMonth]);

  const scopeKindCounts = useMemo(() => {
    const counts: Record<TodayAuditEventKind, number> = {
      capture: 0,
      stored: 0,
      connection: 0,
      review: 0,
      gap: 0,
    };

    if (auditScope === "day" && briefingQuery.data) {
      for (const kind of TODAY_AUDIT_KINDS) {
        counts[kind] = getBriefingCountForKind(briefingQuery.data, kind);
      }
      return counts;
    }

    for (const day of scopeCalendarDays) {
      for (const kind of TODAY_AUDIT_KINDS) {
        counts[kind] += getCalendarDayCountForKind(day, kind);
      }
    }

    return counts;
  }, [auditScope, briefingQuery.data, scopeCalendarDays]);

  const scopeTotals = useMemo(() => {
    return scopeCalendarDays.reduce(
      (acc, day) => {
        const filteredTotal = getCalendarDayTotalForKinds(day, selectedKindSet);

        acc.captures += day.captures;
        acc.stored_cards += day.stored_cards;
        acc.connections += day.connections;
        acc.reviews_due += day.reviews_due;
        acc.reviews_completed += day.reviews_completed;
        acc.gaps += day.gaps;
        acc.total_events += day.total_events;
        acc.filtered_total_events += filteredTotal;

        if (day.total_events > 0) acc.active_days += 1;
        if (filteredTotal > 0) acc.filtered_active_days += 1;

        return acc;
      },
      {
        captures: 0,
        stored_cards: 0,
        connections: 0,
        reviews_due: 0,
        reviews_completed: 0,
        gaps: 0,
        total_events: 0,
        filtered_total_events: 0,
        active_days: 0,
        filtered_active_days: 0,
      },
    );
  }, [scopeCalendarDays, selectedKindSet]);

  const isInitialLoading = !calendarQuery.data && calendarQuery.isLoading;
  const isBriefingLoading = !briefingQuery.data && briefingQuery.isLoading;

  if (isInitialLoading) {
    return (
      <div className="space-y-8">
        <div className="space-y-3">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-12 w-80" />
          <Skeleton className="h-5 w-[32rem]" />
        </div>
        <div className="grid gap-8 xl:grid-cols-[320px_minmax(0,1fr)]">
          <Skeleton className="h-[30rem] w-full rounded-xl" />
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-28 w-full rounded-xl" />
              ))}
            </div>
            <Skeleton className="h-[20rem] w-full rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  if (calendarQuery.isError) {
    return (
      <div className="flex flex-col items-center py-20 text-center">
        <p className="font-serif text-3xl tracking-tight">Could not load your calendar audit</p>
        <p className="mt-3 max-w-xl text-sm text-muted-foreground">
          The daily activity summary endpoint is unavailable. Check that the backend is running.
        </p>
        <Button variant="outline" className="mt-5" onClick={() => void calendarQuery.refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  const briefing = briefingQuery.data;
  const hasDayActivity = (briefing?.stats.total_events ?? 0) > 0;
  const hiddenQuietMonthDays =
    auditScope === "month" ? Math.max(scopeCalendarDays.length - collapsedAuditDays.length, 0) : 0;
  const scopeLabel = formatAuditScopeLabel(auditScope, selectedDate, scopeStart, scopeEnd);
  const isShowingAllKinds = selectedKinds.length === TODAY_AUDIT_KINDS.length;

  return (
    <div className="space-y-8">
      <header className="border-b pb-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--alfred-text-tertiary)]">
              Daily Audit
            </div>
            <div>
              <h1 className="font-serif text-4xl tracking-tight">{formatSelectedDateLabel(selectedDate)}</h1>
              <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                Explore what you captured, distilled, connected, and still owe yourself on{" "}
                {format(selectedDate, "MMMM d, yyyy")}. Alfred keeps the ledger by day so your learning stays inspectable.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={goToPreviousDay}
            >
              <ChevronLeft className="size-4" />
              Previous day
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={goToNextDay}
              disabled={selectedDate >= today}
            >
              Next day
              <ChevronRight className="size-4" />
            </Button>
            <Button size="sm" onClick={goToToday}>Jump to today</Button>
          </div>
        </div>
      </header>

      <div className="grid gap-8 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="space-y-4 xl:sticky xl:top-6 xl:self-start">
          <section className="rounded-xl border bg-card p-4">
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--alfred-text-tertiary)]">
                  Calendar
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  Select any day to audit what landed in Alfred.
                </p>
              </div>
              <div className="rounded-sm border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
                {timeZone}
              </div>
            </div>

            <Calendar
              mode="single"
              month={visibleMonth}
              onMonthChange={setVisibleMonth}
              selected={selectedDate}
              onSelect={(value) => {
                if (!value) return;
                selectDate(value);
              }}
              disabled={{ after: today }}
              modifiers={{
                low: (date) => {
                  const total = activityByDay.get(toIsoDay(date))?.total_events ?? 0;
                  return total >= 1 && total <= 2;
                },
                medium: (date) => {
                  const total = activityByDay.get(toIsoDay(date))?.total_events ?? 0;
                  return total >= 3 && total <= 5;
                },
                high: (date) => (activityByDay.get(toIsoDay(date))?.total_events ?? 0) >= 6,
                reviewHeavy: (date) => (activityByDay.get(toIsoDay(date))?.reviews_due ?? 0) > 0,
              }}
              modifiersClassNames={{
                low: "bg-primary/5 text-foreground",
                medium: "border border-primary/20 bg-primary/10 text-foreground",
                high: "border border-primary/30 bg-primary/15 text-primary",
                reviewHeavy: "ring-1 ring-[var(--warning)]/30",
              }}
              className="w-full rounded-lg border bg-background p-2"
            />

            <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
              <div className="rounded-lg border px-3 py-2">
                <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
                  Active days
                </div>
                <div className="mt-2 font-serif text-2xl leading-none">{monthTotals.active_days}</div>
              </div>
              <div className="rounded-lg border px-3 py-2">
                <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
                  Month events
                </div>
                <div className="mt-2 font-serif text-2xl leading-none">{monthTotals.total_events}</div>
              </div>
            </div>

            <div className="mt-4 border-t pt-4">
              <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
                Heatmap legend
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                <div className="flex items-center gap-2">
                  <span className="size-3 rounded-sm border bg-background" />
                  Quiet
                </div>
                <div className="flex items-center gap-2">
                  <span className="size-3 rounded-sm bg-primary/5" />
                  1-2 events
                </div>
                <div className="flex items-center gap-2">
                  <span className="size-3 rounded-sm border border-primary/20 bg-primary/10" />
                  3-5 events
                </div>
                <div className="flex items-center gap-2">
                  <span className="size-3 rounded-sm border border-primary/30 bg-primary/15" />
                  6+ events
                </div>
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                Amber rings mark days with reviews due.
              </p>
            </div>
          </section>

          <section className="rounded-xl border bg-card p-4">
            <PanelHeader
              title="Month At A Glance"
              subtitle={format(visibleMonth, "MMMM yyyy")}
              count={monthAuditDays.length}
            />
            <div className="mt-4 space-y-2">
              {monthAuditDays.length > 0 ? (
                monthAuditDays.map((day) => (
                  <button
                    key={day.date}
                    type="button"
                    onClick={() => selectDate(parseISO(day.date))}
                    className={cn(
                      "w-full rounded-lg border px-3 py-3 text-left transition-colors hover:border-[var(--border-strong)] hover:bg-[var(--alfred-accent-subtle)]",
                      selectedDayKey === day.date && "border-[var(--border-strong)] bg-[var(--alfred-accent-subtle)]",
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium">{format(parseISO(day.date), "EEE, MMM d")}</span>
                      <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
                        {day.total_events} events
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {day.captures} captures · {day.stored_cards} cards · {day.connections} links · {day.reviews_due} reviews
                    </p>
                  </button>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">
                  No recorded learning activity in this month yet.
                </p>
              )}
            </div>
          </section>
        </aside>

        <main className="space-y-6">
          {isBriefingLoading ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                {Array.from({ length: 5 }).map((_, index) => (
                  <Skeleton key={index} className="h-28 w-full rounded-xl" />
                ))}
              </div>
              <Skeleton className="h-[18rem] w-full rounded-xl" />
            </div>
          ) : briefingQuery.isError || !briefing ? (
            <div className="rounded-xl border bg-card p-6">
              <p className="font-serif text-2xl">Could not load this day</p>
              <p className="mt-2 text-sm text-muted-foreground">
                Alfred could not build the audit for {format(selectedDate, "MMMM d, yyyy")}.
              </p>
              <Button variant="outline" className="mt-4" onClick={() => void briefingQuery.refetch()}>
                Retry
              </Button>
            </div>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <StatCard
                  icon={FileText}
                  label="Captured"
                  value={briefing.stats.total_captures}
                  meta="documents"
                />
                <StatCard
                  icon={NotebookPen}
                  label="Stored"
                  value={briefing.stats.total_cards_created}
                  meta="cards"
                />
                <StatCard
                  icon={GitBranch}
                  label="Connected"
                  value={briefing.stats.total_connections}
                  meta="links"
                />
                <StatCard
                  icon={Brain}
                  label="Reviews"
                  value={briefing.stats.total_reviews_due}
                  meta={`${briefing.stats.total_reviews_completed} cleared`}
                />
                <StatCard
                  icon={Sparkles}
                  label="Gaps"
                  value={briefing.stats.total_gaps}
                  meta="stubs"
                />
              </div>

              <section className="rounded-xl border bg-card p-5">
                <PanelHeader
                  title="Audit Controls"
                  subtitle="Switch between a day ledger and collapsed range summaries, then focus the record on the kinds of learning you want to inspect."
                />
                <div className="mt-4 grid gap-4 xl:grid-cols-[auto_minmax(0,1fr)]">
                  <div>
                    <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
                      Scope
                    </div>
                    <ToggleGroup
                      type="single"
                      value={auditScope}
                      onValueChange={handleScopeChange}
                      variant="outline"
                      size="sm"
                      spacing={1}
                      className="mt-2 flex-wrap"
                    >
                      <ToggleGroupItem value="day">Day</ToggleGroupItem>
                      <ToggleGroupItem value="week">Week</ToggleGroupItem>
                      <ToggleGroupItem value="month">Month</ToggleGroupItem>
                    </ToggleGroup>
                  </div>

                  <div>
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
                        Event filters
                      </div>
                      {!isShowingAllKinds ? (
                        <Button variant="ghost" size="sm" onClick={handleResetKinds}>
                          Show all
                        </Button>
                      ) : null}
                    </div>
                    <ToggleGroup
                      type="multiple"
                      value={selectedKinds}
                      onValueChange={handleKindsChange}
                      variant="outline"
                      size="sm"
                      spacing={1}
                      className="mt-2 flex-wrap"
                    >
                      {TODAY_AUDIT_KINDS.map((kind) => (
                        <ToggleGroupItem key={kind} value={kind}>
                          <span>{AUDIT_KIND_LABELS[kind]}</span>
                          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
                            {scopeKindCounts[kind]}
                          </span>
                        </ToggleGroupItem>
                      ))}
                    </ToggleGroup>
                  </div>
                </div>
              </section>

              <section className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]">
                <div className="rounded-xl border bg-card p-5">
                  <PanelHeader
                    title="Audit Trail"
                    subtitle={
                      auditScope === "day"
                        ? `A single ledger for ${scopeLabel}`
                        : `Collapsed by day for ${scopeLabel}`
                    }
                    count={
                      auditScope === "day"
                        ? formatCountLabel(filteredTimeline.length, "event")
                        : formatCountLabel(scopeTotals.filtered_active_days, "active day")
                    }
                  />
                  <div className="mt-4 space-y-3">
                    {auditScope === "day" ? (
                      filteredTimeline.length > 0 ? (
                        filteredTimeline.map((event) => <TimelineItem key={event.id} event={event} />)
                      ) : (
                        <EmptyPanel
                          title={hasDayActivity ? "Nothing matched these filters" : "Quiet day"}
                          body={
                            hasDayActivity
                              ? "This date has activity in Alfred, but none of it falls inside the selected categories."
                              : "No documents, cards, connections, reviews, or gaps were recorded for this date."
                          }
                        />
                      )
                    ) : collapsedAuditDays.length > 0 ? (
                      <>
                        {collapsedAuditDays.map((day) => (
                          <CollapsedAuditRow
                            key={day.date}
                            day={day}
                            isSelected={day.date === selectedDayKey}
                            selectedKinds={selectedKindSet}
                            onSelectDay={handleDrillIntoDay}
                          />
                        ))}
                        {hiddenQuietMonthDays > 0 ? (
                          <p className="text-xs text-muted-foreground">
                            {formatCountLabel(hiddenQuietMonthDays, "quiet day")} stay visible in the heatmap above.
                          </p>
                        ) : null}
                      </>
                    ) : (
                      <EmptyPanel
                        title={scopeTotals.total_events > 0 ? "No matching days" : "No recorded activity"}
                        body={
                          scopeTotals.total_events > 0
                            ? "This range has activity in Alfred, but none of it matches the selected filters."
                            : "Nothing was captured, stored, connected, reviewed, or surfaced in this range."
                        }
                      />
                    )}
                  </div>
                </div>

                <div className="space-y-4">
                  <section className="rounded-xl border bg-card p-5">
                    <PanelHeader
                      title={auditScope === "day" ? "Day Snapshot" : "Range Snapshot"}
                      subtitle={`${briefing.stats.total_cards} cards in the library · ${briefing.stats.total_links} total links`}
                    />
                    <div className="mt-4 space-y-3 text-sm text-muted-foreground">
                      {auditScope === "day" ? (
                        <>
                          <p>
                            {briefing.stats.total_events > 0
                              ? `${formatSelectedDateLabel(selectedDate)} recorded ${briefing.stats.total_events} auditable events across capture, storage, connection, review, and gap discovery.`
                              : `${formatSelectedDateLabel(selectedDate)} did not create new audit entries.`}
                          </p>
                          <p>
                            {selectedDaySummary && selectedDaySummary.reviews_due > 0
                              ? `${selectedDaySummary.reviews_due} reviews came due on this date, with ${selectedDaySummary.reviews_completed} already cleared.`
                              : "No review debt was scheduled for this date."}
                          </p>
                        </>
                      ) : (
                        <>
                          <p>
                            {scopeTotals.filtered_total_events > 0
                              ? `${scopeLabel} recorded ${scopeTotals.filtered_total_events} events in the selected categories across ${scopeTotals.filtered_active_days} active days.`
                              : `${scopeLabel} did not record anything inside the current filters.`}
                          </p>
                          <p>
                            {scopeTotals.reviews_due > 0
                              ? `${scopeTotals.reviews_due} reviews came due in this range, with ${scopeTotals.reviews_completed} already cleared.`
                              : "No review debt was scheduled in this range."}
                          </p>
                          <p>
                            Detailed artifact lists below stay pinned to {format(selectedDate, "MMMM d, yyyy")}. Click any collapsed row to inspect another day.
                          </p>
                        </>
                      )}
                      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
                        Generated {format(parseISO(briefing.generated_at), "MMM d, yyyy 'at' h:mm a")}
                      </p>
                    </div>
                  </section>

                  <section className="rounded-xl border bg-card p-5">
                    <PanelHeader
                      title="Explore Next"
                      subtitle="Jump directly into the artifacts behind the day."
                    />
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button asChild variant="outline" size="sm">
                        <Link href="/documents">Browse documents</Link>
                      </Button>
                      <Button asChild variant="outline" size="sm">
                        <Link href="/knowledge">Browse knowledge</Link>
                      </Button>
                      <Button asChild variant="outline" size="sm">
                        <Link href="/research">Open research</Link>
                      </Button>
                    </div>
                  </section>
                </div>
              </section>

              {auditScope !== "day" ? (
                <section className="rounded-xl border border-dashed px-4 py-3 text-sm text-muted-foreground">
                  The detailed sections below remain scoped to {format(selectedDate, "MMMM d, yyyy")}. Use the
                  collapsed audit trail above to drill into another day.
                </section>
              ) : null}

              <div className="grid gap-4 xl:grid-cols-2">
                {selectedKindSet.has("capture") ? (
                  <SectionCard
                    title="Captured Documents"
                    subtitle="Source material Alfred ingested that day"
                    count={briefing.captures.length}
                  >
                    {briefing.captures.length > 0 ? (
                      <div className="space-y-2">
                        {briefing.captures.map((capture) => (
                          <Link
                            key={capture.id}
                            href={`/documents/${capture.id}`}
                            className="block rounded-lg border px-4 py-3 transition-colors hover:bg-[var(--alfred-accent-subtle)]"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="truncate text-sm">{capture.title}</p>
                                <p className="mt-1 text-xs text-muted-foreground">
                                  {capture.content_type ?? "capture"} · {formatTimestamp(capture.created_at)}
                                </p>
                              </div>
                              <span className="rounded-sm bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--alfred-text-tertiary)]">
                                {capture.pipeline_status}
                              </span>
                            </div>
                          </Link>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">No documents were captured on this date.</p>
                    )}
                  </SectionCard>
                ) : null}

                {selectedKindSet.has("stored") ? (
                  <SectionCard
                    title="Stored Cards"
                    subtitle="Knowledge you distilled into durable cards"
                    count={briefing.stored_cards.length}
                  >
                    {briefing.stored_cards.length > 0 ? (
                      <div className="space-y-2">
                        {briefing.stored_cards.map((card) => (
                          <Link
                            key={card.card_id}
                            href={`/knowledge/${card.card_id}`}
                            className="block rounded-lg border px-4 py-3 transition-colors hover:bg-[var(--alfred-accent-subtle)]"
                          >
                            <p className="truncate text-sm">{card.title}</p>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {card.topic ?? "Untopiced"} · {card.tags.length > 0 ? card.tags.join(" · ") : "No tags"} ·{" "}
                              {formatTimestamp(card.created_at)}
                            </p>
                          </Link>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">No new knowledge cards were stored on this date.</p>
                    )}
                  </SectionCard>
                ) : null}

                {selectedKindSet.has("connection") ? (
                  <SectionCard
                    title="Connections Made"
                    subtitle="Links added between ideas on this date"
                    count={briefing.connections.length}
                  >
                    {briefing.connections.length > 0 ? (
                      <div className="space-y-2">
                        {briefing.connections.map((connection) => (
                          <div key={connection.link_id} className="rounded-lg border px-4 py-3">
                            <div className="flex items-center gap-2 text-sm">
                              <Link href={`/knowledge/${connection.from_card_id}`} className="truncate hover:text-primary">
                                {connection.from_title}
                              </Link>
                              <span className="text-[var(--alfred-text-tertiary)]">→</span>
                              <Link href={`/knowledge/${connection.to_card_id}`} className="truncate hover:text-primary">
                                {connection.to_title}
                              </Link>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {connection.type} · {formatTimestamp(connection.created_at)}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">No new links were created on this date.</p>
                    )}
                  </SectionCard>
                ) : null}

                {selectedKindSet.has("review") ? (
                  <SectionCard
                    title="Reviews Scheduled"
                    subtitle="Cards Alfred expected you to revisit that day"
                    count={briefing.reviews.length}
                  >
                    {briefing.reviews.length > 0 ? (
                      <div className="space-y-2">
                        {briefing.reviews.map((review) => (
                          <Link
                            key={review.review_id}
                            href={`/knowledge/${review.card_id}`}
                            className="block rounded-lg border px-4 py-3 transition-colors hover:bg-[var(--alfred-accent-subtle)]"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="truncate text-sm">{review.card_title}</p>
                                <p className="mt-1 text-xs text-muted-foreground">
                                  Stage {review.stage} · due {formatTimestamp(review.due_at)}
                                </p>
                              </div>
                              <span className="rounded-sm bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--alfred-text-tertiary)]">
                                {review.status}
                              </span>
                            </div>
                          </Link>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">No review queue was scheduled for this date.</p>
                    )}
                  </SectionCard>
                ) : null}

                {selectedKindSet.has("gap") ? (
                  <SectionCard
                    title="Gaps Surfaced"
                    subtitle="Placeholder cards that still need real thought"
                    count={briefing.gaps.length}
                  >
                    {briefing.gaps.length > 0 ? (
                      <div className="space-y-2">
                        {briefing.gaps.map((gap) => (
                          <Link
                            key={gap.card_id}
                            href={`/knowledge/${gap.card_id}`}
                            className="block rounded-lg border border-dashed px-4 py-3 transition-colors hover:bg-[var(--alfred-accent-subtle)]"
                          >
                            <p className="truncate text-sm">{gap.title}</p>
                            <p className="mt-1 text-xs text-muted-foreground">
                              Stub card · {formatTimestamp(gap.created_at)}
                            </p>
                          </Link>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">No new gaps were surfaced on this date.</p>
                    )}
                  </SectionCard>
                ) : null}
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
