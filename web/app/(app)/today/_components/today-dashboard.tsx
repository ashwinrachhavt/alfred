"use client";

import Link from "next/link";
import { memo, useCallback, useMemo, useState, type ReactNode } from "react";

import { addDays, format, isSameMonth, isToday, isYesterday, parseISO, startOfDay } from "date-fns";
import {
  ArrowRight,
  Brain,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  FileEdit,
  FileText,
  GitBranch,
  ListFilter,
  Menu,
  Network,
  NotebookPen,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Calendar } from "@/components/ui/calendar";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type {
  TodayCalendarDay,
  TodayCaptureItem,
  TodayConnectionItem,
  TodayGapItem,
  TodayReviewItem,
  TodayStoredCardItem,
} from "@/lib/api/today";
import { useBrowserTimeZone } from "@/lib/hooks/use-browser-timezone";
import {
  TODAY_AUDIT_KINDS,
  buildTodayBriefingLines,
  buildTodayInsightCards,
  buildTodayNextActions,
  buildTodayThreads,
  buildTodayTimeline,
  getTodayConnectionDebt,
  getTodayReviewDebt,
  makeCalendarDayMap,
  type TodayAction,
  type TodayAuditEvent,
  type TodayAuditEventKind,
  type TodayInsightCard,
  type TodayInsightTone,
  type TodayThread,
} from "@/features/today/utils";
import { toIsoDay, useTodayBriefing, useTodayCalendar } from "@/features/today/queries";
import { cn } from "@/lib/utils";

const AUDIT_KIND_LABELS: Record<TodayAuditEventKind, string> = {
  capture: "Captures",
  stored: "Cards",
  connection: "Links",
  review: "Reviews",
  gap: "Gaps",
};

const INSIGHT_ICONS: Record<TodayInsightCard["id"], LucideIcon> = {
  capture: FileText,
  stored: NotebookPen,
  connection: Network,
  review: Brain,
  gap: Sparkles,
  notes: FileEdit,
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

function getToneClasses(tone: TodayInsightTone): string {
  switch (tone) {
    case "accent":
      return "border-[var(--alfred-accent-muted)] bg-[var(--alfred-accent-subtle)]";
    case "warning":
      return "border-[var(--warning)]/30 bg-[var(--warning)]/10";
    case "success":
      return "border-[var(--success)]/25 bg-[var(--success)]/10";
    case "neutral":
      return "border-border bg-card";
  }
}

function getDominantCalendarSignal(day: TodayCalendarDay | undefined): string {
  if (!day || day.total_events === 0) return "quiet";

  const signals = [
    { label: "capture", value: day.captures },
    { label: "distillation", value: day.stored_cards },
    { label: "connections", value: day.connections },
    { label: "reviews", value: day.reviews_due },
    { label: "gaps", value: day.gaps },
  ].sort((left, right) => right.value - left.value);

  return signals[0]?.value ? signals[0].label : "mixed activity";
}

function describeCalendarDay(day: TodayCalendarDay | undefined): string {
  if (!day || day.total_events === 0) {
    return "No recorded activity. Use the day for reviews, connection passes, or capture.";
  }

  const connectionDebt =
    day.stored_cards > day.connections ? day.stored_cards - day.connections : 0;
  const reviewDebt =
    day.reviews_due > day.reviews_completed ? day.reviews_due - day.reviews_completed : 0;
  const debt =
    connectionDebt > 0 ? "connection debt high" : reviewDebt > 0 ? "reviews due" : "balanced";

  return `${formatCountLabel(day.total_events, "event")} / main signal: ${getDominantCalendarSignal(
    day,
  )} / ${debt}.`;
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
        <div className="font-mono text-[10px] tracking-[0.16em] text-[var(--alfred-text-tertiary)] uppercase">
          {title}
        </div>
        {subtitle ? <p className="text-muted-foreground mt-2 text-sm">{subtitle}</p> : null}
      </div>
      {count !== undefined ? (
        <span className="text-primary rounded-sm border bg-[var(--alfred-accent-subtle)] px-2 py-1 font-mono text-[10px] tracking-[0.12em] uppercase">
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
    <section className="bg-card rounded-lg border p-5">
      <PanelHeader title={title} subtitle={subtitle} count={count} />
      <div className="mt-4">{children}</div>
    </section>
  );
}

function EmptyPanel({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-dashed p-6 text-center">
      <p className="font-serif text-xl">{title}</p>
      <p className="text-muted-foreground mt-2 text-sm">{body}</p>
    </div>
  );
}

const TimelineItem = memo(function TimelineItem({ event }: { event: TodayAuditEvent }) {
  const kindMeta: Record<TodayAuditEventKind, { icon: LucideIcon; label: string }> = {
    capture: { icon: FileText, label: "Captured" },
    stored: { icon: NotebookPen, label: "Stored" },
    connection: { icon: GitBranch, label: "Connected" },
    review: { icon: Brain, label: "Review" },
    gap: { icon: Sparkles, label: "Gap" },
  };

  const meta = kindMeta[event.kind];
  const Icon = meta.icon;

  return (
    <div className="grid gap-3 rounded-lg border px-3 py-3 md:grid-cols-[auto_minmax(0,1fr)]">
      <div className="text-primary flex size-8 items-center justify-center rounded-sm bg-[var(--alfred-accent-subtle)]">
        <Icon className="size-4" />
      </div>
      <div className="min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[10px] tracking-[0.16em] text-[var(--alfred-text-tertiary)] uppercase">
            {meta.label}
          </span>
          <span className="font-mono text-[10px] tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
            {formatTimestamp(event.timestamp)}
          </span>
        </div>
        <Link href={event.href} className="hover:text-primary mt-1 block truncate text-sm">
          {event.title}
        </Link>
        <p className="text-muted-foreground mt-1 text-xs">{event.meta}</p>
      </div>
    </div>
  );
});

const InsightCard = memo(function InsightCard({ insight }: { insight: TodayInsightCard }) {
  const Icon = INSIGHT_ICONS[insight.id];

  return (
    <Card className={cn("gap-4 rounded-lg py-5 shadow-none", getToneClasses(insight.tone))}>
      <CardHeader className="px-5">
        <div className="flex items-center justify-between gap-3">
          <div className="font-mono text-[10px] tracking-[0.16em] text-[var(--alfred-text-tertiary)] uppercase">
            {insight.label}
          </div>
          <Icon className="size-4 text-[var(--alfred-text-tertiary)]" />
        </div>
        <CardTitle className="font-serif text-3xl leading-none font-normal tabular-nums">
          {insight.value}
        </CardTitle>
        <CardDescription className="font-mono text-[10px] tracking-[0.12em] uppercase">
          {insight.metric}
        </CardDescription>
      </CardHeader>
      <CardContent className="px-5">
        <p className="text-muted-foreground text-sm">{insight.body}</p>
      </CardContent>
    </Card>
  );
});

const ActionCard = memo(function ActionCard({ action }: { action: TodayAction }) {
  return (
    <Card className={cn("rounded-lg py-5 shadow-none", getToneClasses(action.tone))}>
      <CardHeader className="gap-3 px-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="text-base leading-snug font-medium">{action.title}</CardTitle>
            <CardDescription className="mt-2">{action.body}</CardDescription>
          </div>
          <ArrowRight className="mt-0.5 size-4 shrink-0 text-[var(--alfred-text-tertiary)]" />
        </div>
      </CardHeader>
      <CardContent className="px-5">
        <Button asChild size="sm" variant={action.tone === "warning" ? "default" : "outline"}>
          <Link href={action.href}>{action.cta}</Link>
        </Button>
      </CardContent>
    </Card>
  );
});

const ThreadRow = memo(function ThreadRow({ thread }: { thread: TodayThread }) {
  return (
    <div className="rounded-lg border px-4 py-3">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{thread.name}</p>
          <p className="text-muted-foreground mt-1 text-xs">
            {formatCountLabel(thread.cards, "card")} / {formatCountLabel(thread.links, "link")} /{" "}
            {formatCountLabel(thread.reviews, "review")}
          </p>
        </div>
        <Badge
          variant="outline"
          className="rounded-sm font-mono text-[10px] tracking-[0.1em] uppercase"
        >
          {thread.status}
        </Badge>
      </div>
    </div>
  );
});

const MonthDayButton = memo(function MonthDayButton({
  day,
  isSelected,
  onSelectDate,
}: {
  day: TodayCalendarDay;
  isSelected: boolean;
  onSelectDate: (date: Date) => void;
}) {
  const handleClick = useCallback(() => {
    onSelectDate(parseISO(day.date));
  }, [day.date, onSelectDate]);

  return (
    <button
      type="button"
      onClick={handleClick}
      className={cn(
        "w-full rounded-lg border px-3 py-3 text-left transition-colors hover:border-[var(--border-strong)] hover:bg-[var(--alfred-accent-subtle)]",
        isSelected && "border-[var(--border-strong)] bg-[var(--alfred-accent-subtle)]",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="font-medium">{format(parseISO(day.date), "EEE, MMM d")}</span>
        <span className="font-mono text-[10px] tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
          {day.total_events} events
        </span>
      </div>
      <p className="text-muted-foreground mt-2 text-xs">{describeCalendarDay(day)}</p>
    </button>
  );
});

const CaptureItem = memo(function CaptureItem({ capture }: { capture: TodayCaptureItem }) {
  return (
    <Link
      href={`/documents/${capture.id}`}
      className="block rounded-lg border px-4 py-3 transition-colors hover:bg-[var(--alfred-accent-subtle)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm">{capture.title}</p>
          <p className="text-muted-foreground mt-1 text-xs">
            {capture.content_type ?? "capture"} / {formatTimestamp(capture.created_at)}
          </p>
        </div>
        <Badge variant="outline" className="rounded-sm font-mono text-[10px] uppercase">
          {capture.pipeline_status}
        </Badge>
      </div>
    </Link>
  );
});

const StoredCardItem = memo(function StoredCardItem({ card }: { card: TodayStoredCardItem }) {
  return (
    <Link
      href={`/knowledge/${card.card_id}`}
      className="block rounded-lg border px-4 py-3 transition-colors hover:bg-[var(--alfred-accent-subtle)]"
    >
      <p className="truncate text-sm">{card.title}</p>
      <p className="text-muted-foreground mt-1 text-xs">
        {card.topic ?? "Untopiced"} / {card.tags.length > 0 ? card.tags.join(" / ") : "No tags"} /{" "}
        {formatTimestamp(card.created_at)}
      </p>
    </Link>
  );
});

const ConnectionItem = memo(function ConnectionItem({
  connection,
}: {
  connection: TodayConnectionItem;
}) {
  return (
    <div className="rounded-lg border px-4 py-3">
      <div className="flex items-center gap-2 text-sm">
        <Link
          href={`/knowledge/${connection.from_card_id}`}
          className="hover:text-primary truncate"
        >
          {connection.from_title}
        </Link>
        <span className="text-[var(--alfred-text-tertiary)]">-&gt;</span>
        <Link href={`/knowledge/${connection.to_card_id}`} className="hover:text-primary truncate">
          {connection.to_title}
        </Link>
      </div>
      <p className="text-muted-foreground mt-1 text-xs">
        {connection.type} / {formatTimestamp(connection.created_at)}
      </p>
    </div>
  );
});

const ReviewItem = memo(function ReviewItem({ review }: { review: TodayReviewItem }) {
  return (
    <Link
      href={`/knowledge/${review.card_id}`}
      className="block rounded-lg border px-4 py-3 transition-colors hover:bg-[var(--alfred-accent-subtle)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm">{review.card_title}</p>
          <p className="text-muted-foreground mt-1 text-xs">
            Stage {review.stage} / due {formatTimestamp(review.due_at)}
          </p>
        </div>
        <Badge variant="outline" className="rounded-sm font-mono text-[10px] uppercase">
          {review.status}
        </Badge>
      </div>
    </Link>
  );
});

const GapItem = memo(function GapItem({ gap }: { gap: TodayGapItem }) {
  return (
    <Link
      href={`/knowledge/${gap.card_id}`}
      className="block rounded-lg border border-dashed px-4 py-3 transition-colors hover:bg-[var(--alfred-accent-subtle)]"
    >
      <p className="truncate text-sm">{gap.title}</p>
      <p className="text-muted-foreground mt-1 text-xs">
        Stub card / {formatTimestamp(gap.created_at)}
      </p>
    </Link>
  );
});

function AuditRail({
  filteredTimeline,
  selectedKinds,
  onKindsChange,
  onResetKinds,
  isShowingAllKinds,
  hasDayActivity,
  isLoading,
  selectedDate,
}: {
  filteredTimeline: TodayAuditEvent[];
  selectedKinds: TodayAuditEventKind[];
  onKindsChange: (value: string[]) => void;
  onResetKinds: () => void;
  isShowingAllKinds: boolean;
  hasDayActivity: boolean;
  isLoading: boolean;
  selectedDate: Date;
}) {
  return (
    <section className="bg-card flex max-h-[calc(100vh-7rem)] flex-col rounded-lg border">
      <div className="border-b p-4">
        <PanelHeader
          title="Audit Trail"
          subtitle={`${format(selectedDate, "MMMM d, yyyy")} / ${formatCountLabel(
            filteredTimeline.length,
            "visible event",
          )}`}
        />

        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
              <ListFilter className="size-3.5" />
              Filters
            </div>
            {!isShowingAllKinds ? (
              <Button variant="ghost" size="sm" onClick={onResetKinds}>
                Show all
              </Button>
            ) : null}
          </div>
          <ToggleGroup
            type="multiple"
            value={selectedKinds}
            onValueChange={onKindsChange}
            variant="outline"
            size="sm"
            spacing={1}
            className="w-full flex-wrap justify-start"
          >
            {TODAY_AUDIT_KINDS.map((kind) => (
              <ToggleGroupItem key={kind} value={kind} className="min-w-[6.75rem] justify-center">
                {AUDIT_KIND_LABELS[kind]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <div className="space-y-3">
          {isLoading ? (
            Array.from({ length: 5 }).map((_, index) => (
              <Skeleton key={index} className="h-24 w-full rounded-lg" />
            ))
          ) : filteredTimeline.length > 0 ? (
            filteredTimeline.map((event) => <TimelineItem key={event.id} event={event} />)
          ) : (
            <EmptyPanel
              title={hasDayActivity ? "Nothing matched" : "Quiet day"}
              body={
                hasDayActivity
                  ? "This date has activity, but none of it matches the selected filters."
                  : "No documents, cards, links, reviews, or gaps were recorded for this date."
              }
            />
          )}
        </div>
      </div>
    </section>
  );
}

function CalendarAside({
  activityByDay,
  monthAuditDays,
  monthTotals,
  selectedDate,
  selectedDayKey,
  selectedDaySummary,
  timeZone,
  today,
  visibleMonth,
  onMonthChange,
  onSelectDate,
}: {
  activityByDay: Map<string, TodayCalendarDay>;
  monthAuditDays: TodayCalendarDay[];
  monthTotals: {
    active_days: number;
    total_events: number;
  };
  selectedDate: Date;
  selectedDayKey: string;
  selectedDaySummary: TodayCalendarDay | undefined;
  timeZone: string;
  today: Date;
  visibleMonth: Date;
  onMonthChange: (date: Date) => void;
  onSelectDate: (date: Date) => void;
}) {
  return (
    <aside className="space-y-4 xl:sticky xl:top-6 xl:self-start">
      <section className="bg-card rounded-lg border p-4">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <div className="font-mono text-[10px] tracking-[0.16em] text-[var(--alfred-text-tertiary)] uppercase">
              Calendar
            </div>
            <p className="text-muted-foreground mt-2 text-sm">
              Select a day to see what matters about it.
            </p>
          </div>
          <div className="rounded-sm border px-2 py-1 font-mono text-[10px] tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
            {timeZone}
          </div>
        </div>

        <Calendar
          mode="single"
          month={visibleMonth}
          onMonthChange={onMonthChange}
          selected={selectedDate}
          onSelect={(value) => {
            if (!value) return;
            onSelectDate(value);
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
          className="bg-background w-full rounded-lg border p-2"
        />

        <div className="mt-4 rounded-lg border bg-[var(--alfred-accent-subtle)] p-3">
          <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
            <CalendarDays className="size-3.5" />
            Why this day matters
          </div>
          <p className="mt-2 text-sm">{format(selectedDate, "MMM d")}</p>
          <p className="text-muted-foreground mt-1 text-xs">
            {describeCalendarDay(selectedDaySummary)}
          </p>
        </div>

        <div className="text-muted-foreground mt-4 grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg border px-3 py-2">
            <div className="font-mono text-[10px] tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
              Active days
            </div>
            <div className="mt-2 font-serif text-2xl leading-none">{monthTotals.active_days}</div>
          </div>
          <div className="rounded-lg border px-3 py-2">
            <div className="font-mono text-[10px] tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
              Month events
            </div>
            <div className="mt-2 font-serif text-2xl leading-none">{monthTotals.total_events}</div>
          </div>
        </div>
      </section>

      <section className="bg-card rounded-lg border p-4">
        <PanelHeader
          title="Month Signals"
          subtitle={format(visibleMonth, "MMMM yyyy")}
          count={monthAuditDays.length}
        />
        <div className="mt-4 space-y-2">
          {monthAuditDays.length > 0 ? (
            monthAuditDays.map((day) => (
              <MonthDayButton
                key={day.date}
                day={day}
                isSelected={selectedDayKey === day.date}
                onSelectDate={onSelectDate}
              />
            ))
          ) : (
            <p className="text-muted-foreground text-sm">
              No recorded learning activity in this month yet.
            </p>
          )}
        </div>
      </section>
    </aside>
  );
}

function ReviewQueuePanel({
  reviews,
  reviewDebt,
  date,
}: {
  reviews: TodayReviewItem[];
  reviewDebt: number;
  date: string;
}) {
  return (
    <section className="bg-card rounded-lg border p-5">
      <PanelHeader
        title="Due Reviews"
        subtitle={
          reviewDebt > 0
            ? `${formatCountLabel(reviewDebt, "card")} need attention.`
            : "No review debt remains for this date."
        }
        count={reviews.length}
      />
      <div className="mt-4 flex flex-wrap gap-2">
        <Button asChild size="sm">
          <Link href={`/today?view=table&date=${date}`}>Start review session</Link>
        </Button>
        <Button asChild size="sm" variant="outline">
          <Link href="/knowledge">Open knowledge</Link>
        </Button>
      </div>
      <div className="mt-4 space-y-2">
        {reviews.length > 0 ? (
          reviews.map((review) => <ReviewItem key={review.review_id} review={review} />)
        ) : (
          <EmptyPanel
            title="No reviews due"
            body="Use the time for a connection pass or a synthesis pass on recent cards."
          />
        )}
      </div>
    </section>
  );
}

function ConnectionDebtPanel({
  cards,
  connectionDebt,
}: {
  cards: TodayStoredCardItem[];
  connectionDebt: number;
}) {
  return (
    <section className="bg-card rounded-lg border p-5">
      <PanelHeader
        title="Unconnected Knowledge"
        subtitle={
          connectionDebt > 0
            ? `${formatCountLabel(connectionDebt, "new card")} need a connection pass.`
            : "New cards have matching link activity."
        }
        count={connectionDebt}
      />
      <div className="mt-4 flex flex-wrap gap-2">
        <Button asChild size="sm" variant={connectionDebt > 0 ? "default" : "outline"}>
          <Link href="/knowledge">Open connection pass</Link>
        </Button>
      </div>
      <div className="mt-4 space-y-2">
        {cards.length > 0 ? (
          cards.slice(0, 5).map((card) => <StoredCardItem key={card.card_id} card={card} />)
        ) : (
          <EmptyPanel
            title="No new cards"
            body="There is nothing new to connect from this selected day."
          />
        )}
      </div>
    </section>
  );
}

export function TodayDashboard() {
  const today = startOfDay(new Date());
  const [selectedDate, setSelectedDate] = useState(today);
  const [visibleMonth, setVisibleMonth] = useState(today);
  const [selectedKinds, setSelectedKinds] = useState<TodayAuditEventKind[]>(TODAY_AUDIT_KINDS);
  const timeZone = useBrowserTimeZone();

  const selectDate = useCallback((value: Date) => {
    const normalized = startOfDay(value);
    setSelectedDate(normalized);
    setVisibleMonth(normalized);
  }, []);

  const handleKindsChange = useCallback((value: string[]) => {
    if (value.length === 0) return;
    setSelectedKinds(value as TodayAuditEventKind[]);
  }, []);

  const handleResetKinds = useCallback(() => {
    setSelectedKinds(TODAY_AUDIT_KINDS);
  }, []);

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
          acc.total_events += day.total_events;
          if (day.total_events > 0) acc.active_days += 1;
          return acc;
        },
        {
          active_days: 0,
          total_events: 0,
        },
      );
  }, [calendarQuery.data?.days, visibleMonth]);

  const briefing = briefingQuery.data;
  const briefingLines = useMemo(
    () => (briefing ? buildTodayBriefingLines(briefing) : []),
    [briefing],
  );
  const insights = useMemo(() => (briefing ? buildTodayInsightCards(briefing) : []), [briefing]);
  const nextActions = useMemo(() => (briefing ? buildTodayNextActions(briefing) : []), [briefing]);
  const threads = useMemo(() => (briefing ? buildTodayThreads(briefing) : []), [briefing]);
  const connectionDebt = briefing ? getTodayConnectionDebt(briefing) : 0;
  const reviewDebt = briefing ? getTodayReviewDebt(briefing) : 0;

  const isInitialLoading = !calendarQuery.data && calendarQuery.isLoading;
  const isBriefingLoading = !briefing && briefingQuery.isLoading;
  const hasDayActivity = (briefing?.stats.total_events ?? 0) > 0;
  const isShowingAllKinds = selectedKinds.length === TODAY_AUDIT_KINDS.length;

  if (isInitialLoading) {
    return (
      <div className="space-y-8">
        <div className="space-y-3">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-12 w-80" />
          <Skeleton className="h-5 w-[32rem]" />
        </div>
        <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)_340px]">
          <Skeleton className="h-[32rem] w-full rounded-lg" />
          <div className="space-y-4">
            <Skeleton className="h-[14rem] w-full rounded-lg" />
            <div className="grid gap-3 md:grid-cols-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-32 w-full rounded-lg" />
              ))}
            </div>
          </div>
          <Skeleton className="hidden h-[32rem] w-full rounded-lg xl:block" />
        </div>
      </div>
    );
  }

  if (calendarQuery.isError) {
    return (
      <div className="flex flex-col items-center py-20 text-center">
        <p className="font-serif text-3xl tracking-tight">Could not load your calendar audit</p>
        <p className="text-muted-foreground mt-3 max-w-xl text-sm">
          The daily activity summary endpoint is unavailable. Check that the backend is running.
        </p>
        <Button variant="outline" className="mt-5" onClick={() => void calendarQuery.refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <header className="border-b pb-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <div className="font-mono text-[10px] tracking-[0.18em] text-[var(--alfred-text-tertiary)] uppercase">
              Daily Briefing
            </div>
            <div>
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h1 className="font-serif text-4xl tracking-tight">Today</h1>
                <span className="font-mono text-[11px] tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
                  {formatSelectedDateLabel(selectedDate)} / {format(selectedDate, "MMMM d, yyyy")}
                </span>
              </div>
              <div className="text-muted-foreground mt-3 max-w-3xl space-y-1 text-sm">
                {briefingLines.length > 0 ? (
                  briefingLines.map((line) => <p key={line}>{line}</p>)
                ) : (
                  <p>Loading the daily briefing for {format(selectedDate, "MMMM d, yyyy")}.</p>
                )}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={goToPreviousDay}>
              <ChevronLeft className="size-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={goToNextDay}
              disabled={selectedDate >= today}
            >
              Next
              <ChevronRight className="size-4" />
            </Button>
            <Button size="sm" onClick={goToToday}>
              Jump to today
            </Button>
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline" size="sm" className="xl:hidden">
                  <Menu className="size-4" />
                  Audit
                </Button>
              </SheetTrigger>
              <SheetContent className="w-[min(92vw,28rem)] p-0 sm:max-w-md">
                <SheetHeader className="border-b">
                  <SheetTitle>Audit Trail</SheetTitle>
                  <SheetDescription>
                    Filter and inspect the raw events for this day.
                  </SheetDescription>
                </SheetHeader>
                <div className="min-h-0 flex-1 p-4">
                  <AuditRail
                    filteredTimeline={filteredTimeline}
                    selectedKinds={selectedKinds}
                    onKindsChange={handleKindsChange}
                    onResetKinds={handleResetKinds}
                    isShowingAllKinds={isShowingAllKinds}
                    hasDayActivity={hasDayActivity}
                    isLoading={isBriefingLoading}
                    selectedDate={selectedDate}
                  />
                </div>
              </SheetContent>
            </Sheet>
          </div>
        </div>
      </header>

      <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)_340px]">
        <CalendarAside
          activityByDay={activityByDay}
          monthAuditDays={monthAuditDays}
          monthTotals={monthTotals}
          selectedDate={selectedDate}
          selectedDayKey={selectedDayKey}
          selectedDaySummary={selectedDaySummary}
          timeZone={timeZone}
          today={today}
          visibleMonth={visibleMonth}
          onMonthChange={setVisibleMonth}
          onSelectDate={selectDate}
        />

        <main className="min-w-0 space-y-6">
          {isBriefingLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-[14rem] w-full rounded-lg" />
              <div className="grid gap-3 md:grid-cols-2">
                {Array.from({ length: 4 }).map((_, index) => (
                  <Skeleton key={index} className="h-32 w-full rounded-lg" />
                ))}
              </div>
            </div>
          ) : briefingQuery.isError || !briefing ? (
            <div className="bg-card rounded-lg border p-6">
              <p className="font-serif text-2xl">Could not load this day</p>
              <p className="text-muted-foreground mt-2 text-sm">
                Alfred could not build the briefing for {format(selectedDate, "MMMM d, yyyy")}.
              </p>
              <Button
                variant="outline"
                className="mt-4"
                onClick={() => void briefingQuery.refetch()}
              >
                Retry
              </Button>
            </div>
          ) : (
            <Tabs defaultValue="briefing" className="space-y-6">
              <TabsList className="rounded-sm">
                <TabsTrigger value="briefing">Briefing</TabsTrigger>
                <TabsTrigger value="review">Review Queue</TabsTrigger>
                <TabsTrigger value="ledger">Ledger</TabsTrigger>
              </TabsList>

              <TabsContent value="briefing" className="space-y-6">
                <section className="space-y-3">
                  <PanelHeader
                    title="Next Best Actions"
                    subtitle="The highest-leverage work Alfred sees from this day."
                    count={nextActions.length}
                  />
                  <div className="grid gap-3 md:grid-cols-2">
                    {nextActions.map((action) => (
                      <ActionCard key={action.id} action={action} />
                    ))}
                  </div>
                </section>

                <section className="space-y-3">
                  <PanelHeader
                    title="Interpreted Signals"
                    subtitle="The numbers with their product meaning attached."
                  />
                  <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
                    {insights.map((insight) => (
                      <InsightCard key={insight.id} insight={insight} />
                    ))}
                  </div>
                </section>

                <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.8fr)]">
                  <div className="bg-card rounded-lg border p-5">
                    <PanelHeader
                      title="Knowledge Threads"
                      subtitle="Themes from the selected day's cards, links, reviews, and gaps."
                      count={threads.length}
                    />
                    <div className="mt-4 space-y-2">
                      {threads.length > 0 ? (
                        threads.map((thread) => <ThreadRow key={thread.id} thread={thread} />)
                      ) : (
                        <EmptyPanel
                          title="No thread signal yet"
                          body="Capture, distill, or connect a few cards to give Alfred something to cluster."
                        />
                      )}
                    </div>
                  </div>

                  <div className="space-y-4">
                    <Card
                      className={cn(
                        "rounded-lg py-5 shadow-none",
                        getToneClasses(connectionDebt > 0 ? "warning" : "success"),
                      )}
                    >
                      <CardHeader className="px-5">
                        <CardTitle className="font-serif text-2xl font-normal">
                          Connection Debt
                        </CardTitle>
                        <CardDescription>
                          {connectionDebt > 0
                            ? `${formatCountLabel(
                                connectionDebt,
                                "card",
                              )} need stronger graph placement.`
                            : "New cards have matching link activity."}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="px-5">
                        <Button
                          asChild
                          size="sm"
                          variant={connectionDebt > 0 ? "default" : "outline"}
                        >
                          <Link href="/knowledge">Open connection pass</Link>
                        </Button>
                      </CardContent>
                    </Card>

                    <Card
                      className={cn(
                        "rounded-lg py-5 shadow-none",
                        getToneClasses(reviewDebt > 0 ? "warning" : "success"),
                      )}
                    >
                      <CardHeader className="px-5">
                        <CardTitle className="font-serif text-2xl font-normal">
                          Review Queue
                        </CardTitle>
                        <CardDescription>
                          {reviewDebt > 0
                            ? `${formatCountLabel(reviewDebt, "review")} still need attention.`
                            : "Nothing is waiting in the review lane."}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="px-5">
                        <Button asChild size="sm" variant="outline">
                          <Link href={`/today?view=table&date=${briefing.date}`}>Open reviews</Link>
                        </Button>
                      </CardContent>
                    </Card>
                  </div>
                </section>
              </TabsContent>

              <TabsContent value="review" className="space-y-6">
                <ReviewQueuePanel
                  reviews={briefing.reviews}
                  reviewDebt={reviewDebt}
                  date={briefing.date}
                />
                <ConnectionDebtPanel
                  cards={briefing.stored_cards}
                  connectionDebt={connectionDebt}
                />
                <SectionCard
                  title="Gaps To Fill"
                  subtitle="Placeholder cards that still need real thought"
                  count={briefing.gaps.length}
                >
                  {briefing.gaps.length > 0 ? (
                    <div className="space-y-2">
                      {briefing.gaps.map((gap) => (
                        <GapItem key={gap.card_id} gap={gap} />
                      ))}
                    </div>
                  ) : (
                    <EmptyPanel
                      title="No surfaced gaps"
                      body="The selected day did not create any stub cards."
                    />
                  )}
                </SectionCard>
              </TabsContent>

              <TabsContent value="ledger" className="space-y-6">
                <div className="text-muted-foreground rounded-lg border border-dashed px-4 py-3 text-sm">
                  Raw artifact lists stay available here. The audit trail remains in the side rail
                  so this tab can focus on the underlying objects.
                </div>

                <div className="grid gap-4 2xl:grid-cols-2">
                  <SectionCard
                    title="Captured Documents"
                    subtitle="Source material Alfred ingested that day"
                    count={briefing.captures.length}
                  >
                    {briefing.captures.length > 0 ? (
                      <div className="space-y-2">
                        {briefing.captures.map((capture) => (
                          <CaptureItem key={capture.id} capture={capture} />
                        ))}
                      </div>
                    ) : (
                      <EmptyPanel
                        title="No documents captured"
                        body="No source material was captured on this date."
                      />
                    )}
                  </SectionCard>

                  <SectionCard
                    title="Stored Cards"
                    subtitle="Knowledge distilled into durable cards"
                    count={briefing.stored_cards.length}
                  >
                    {briefing.stored_cards.length > 0 ? (
                      <div className="space-y-2">
                        {briefing.stored_cards.map((card) => (
                          <StoredCardItem key={card.card_id} card={card} />
                        ))}
                      </div>
                    ) : (
                      <EmptyPanel
                        title="No cards stored"
                        body="No new knowledge cards were stored on this date."
                      />
                    )}
                  </SectionCard>

                  <SectionCard
                    title="Connections Made"
                    subtitle="Links added between ideas on this date"
                    count={briefing.connections.length}
                  >
                    {briefing.connections.length > 0 ? (
                      <div className="space-y-2">
                        {briefing.connections.map((connection) => (
                          <ConnectionItem key={connection.link_id} connection={connection} />
                        ))}
                      </div>
                    ) : (
                      <EmptyPanel
                        title="No links created"
                        body="This is the clearest signal for a connection pass."
                      />
                    )}
                  </SectionCard>

                  <SectionCard
                    title="Reviews Scheduled"
                    subtitle="Cards Alfred expected you to revisit that day"
                    count={briefing.reviews.length}
                  >
                    {briefing.reviews.length > 0 ? (
                      <div className="space-y-2">
                        {briefing.reviews.map((review) => (
                          <ReviewItem key={review.review_id} review={review} />
                        ))}
                      </div>
                    ) : (
                      <EmptyPanel
                        title="No review queue"
                        body="No review queue was scheduled for this date."
                      />
                    )}
                  </SectionCard>

                  <SectionCard
                    title="Gaps Surfaced"
                    subtitle="Placeholder cards that still need real thought"
                    count={briefing.gaps.length}
                  >
                    {briefing.gaps.length > 0 ? (
                      <div className="space-y-2">
                        {briefing.gaps.map((gap) => (
                          <GapItem key={gap.card_id} gap={gap} />
                        ))}
                      </div>
                    ) : (
                      <EmptyPanel
                        title="No gaps surfaced"
                        body="No new stub cards were created on this date."
                      />
                    )}
                  </SectionCard>
                </div>
              </TabsContent>
            </Tabs>
          )}
        </main>

        <aside className="hidden xl:sticky xl:top-6 xl:block xl:self-start">
          <AuditRail
            filteredTimeline={filteredTimeline}
            selectedKinds={selectedKinds}
            onKindsChange={handleKindsChange}
            onResetKinds={handleResetKinds}
            isShowingAllKinds={isShowingAllKinds}
            hasDayActivity={hasDayActivity}
            isLoading={isBriefingLoading}
            selectedDate={selectedDate}
          />
        </aside>
      </div>
    </div>
  );
}
