"use client";

import Link from "next/link";
import * as React from "react";

import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  rectSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, LayoutDashboard, Plus, RotateCcw } from "lucide-react";

import { useRecentCompanyResearchReports } from "@/features/company/queries";
import { useRecentDocuments } from "@/features/documents/queries";
import { useFollowUps } from "@/features/follow-ups/follow-up-provider";
import { useThreads } from "@/features/threads/queries";
import { useNowMs } from "@/hooks/use-now";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  defaultDashboardLayout,
  loadDashboardLayout,
  saveDashboardLayout,
  type DashboardWidgetKey,
} from "@/features/dashboard/dashboard-layout";

function formatTimestamp(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return null;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(date);
}

function formatDueTimestamp(value: string | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return null;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(date);
}

type DashboardWidgetFrameProps = {
  title: string;
  description?: string;
  isEditing: boolean;
  dragHandleProps?: React.HTMLAttributes<HTMLButtonElement>;
  onHide?: () => void;
  children: React.ReactNode;
};

function DashboardWidgetFrame({
  title,
  description,
  isEditing,
  dragHandleProps,
  onHide,
  children,
}: DashboardWidgetFrameProps) {
  return (
    <Card className={cn(isEditing ? "ring-ring/30 ring-1" : null)}>
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
        <div className="space-y-1">
          <CardTitle className="text-base">{title}</CardTitle>
          {description ? <p className="text-muted-foreground text-sm">{description}</p> : null}
        </div>
        {isEditing ? (
          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="text-muted-foreground hover:text-foreground"
              aria-label="Drag widget"
              {...dragHandleProps}
            >
              <GripVertical className="h-4 w-4" aria-hidden="true" />
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={onHide}>
              Hide
            </Button>
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  );
}

function SortableWidget({
  id,
  disabled,
  children,
}: {
  id: DashboardWidgetKey;
  disabled: boolean;
  children: (props: {
    dragHandleProps: React.HTMLAttributes<HTMLButtonElement>;
    isDragging: boolean;
  }) => React.ReactNode;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id,
    disabled,
  });

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(isDragging ? "opacity-90" : null)}
    >
      {children({ dragHandleProps: { ...attributes, ...listeners }, isDragging })}
    </div>
  );
}

export function DashboardClient() {
  const recentDocuments = useRecentDocuments(6);
  const recentReports = useRecentCompanyResearchReports(6);
  const threads = useThreads();
  const {
    items: followUpItems,
    dueNowCount: followUpDueNowCount,
    openCount: followUpOpenCount,
    setFollowUpCenterOpen,
  } = useFollowUps();
  const nowMs = useNowMs(60_000);

  const widgetLabels = React.useMemo<Record<DashboardWidgetKey, string>>(
    () => ({
      "recent-documents": "Recent documents",
      "company-research": "Company research",
      threads: "Threads",
      "follow-ups": "Follow-ups",
      templates: "Templates",
    }),
    [],
  );

  const [isEditing, setIsEditing] = React.useState(false);
  const [layout, setLayout] = React.useState(() =>
    loadDashboardLayout([
      "recent-documents",
      "company-research",
      "threads",
      "follow-ups",
      "templates",
    ]),
  );

  React.useEffect(() => {
    saveDashboardLayout(layout);
  }, [layout]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const visibleKeys = React.useMemo(
    () => layout.order.filter((key) => !layout.hidden.has(key)),
    [layout.hidden, layout.order],
  );

  const hiddenKeys = React.useMemo(
    () => layout.order.filter((key) => layout.hidden.has(key)),
    [layout.hidden, layout.order],
  );

  const sortedThreads = React.useMemo(() => {
    const items = threads.data ?? [];

    return items
      .slice()
      .sort((a, b) => {
        const aTime = a.updated_at
          ? Date.parse(a.updated_at)
          : a.created_at
            ? Date.parse(a.created_at)
            : 0;
        const bTime = b.updated_at
          ? Date.parse(b.updated_at)
          : b.created_at
            ? Date.parse(b.created_at)
            : 0;
        return bTime - aTime;
      })
      .slice(0, 6);
  }, [threads.data]);

  const visibleFollowUps = React.useMemo(() => {
    return followUpItems
      .filter((item) => !item.completedAt)
      .filter((item) => {
        if (!item.snoozedUntil) return true;
        const until = Date.parse(item.snoozedUntil);
        if (Number.isNaN(until)) return true;
        return until <= nowMs;
      })
      .slice()
      .sort((a, b) => {
        const aDue = a.dueAt ? Date.parse(a.dueAt) : Number.POSITIVE_INFINITY;
        const bDue = b.dueAt ? Date.parse(b.dueAt) : Number.POSITIVE_INFINITY;
        if (aDue !== bDue) return aDue - bDue;
        return b.createdAt.localeCompare(a.createdAt);
      })
      .slice(0, 5);
  }, [followUpItems, nowMs]);

  const templates: Array<{ title: string; description: string; href: string }> = [
    {
      title: "Company research",
      description: "Generate a brief with citations.",
      href: "/company",
    },
    {
      title: "System design session",
      description: "Start with a pre-filled problem statement.",
      href: "/system-design?problemStatement=Design%20a%20rate%20limiter%20for%20an%20API",
    },
    {
      title: "Thread: meeting notes",
      description: "Create a thread with a title.",
      href: "/threads?title=Meeting%20notes",
    },
    {
      title: "Follow-up: send recap",
      description: "Create a follow-up due tomorrow.",
      href: "/follow-ups?title=Send%20recap%20email&dueInMinutes=1440",
    },
    { title: "Scan Gmail + Calendar", description: "Fetch previews on demand.", href: "/calendar" },
  ];

  function renderWidget(
    key: DashboardWidgetKey,
    frame: Pick<DashboardWidgetFrameProps, "dragHandleProps" | "isEditing" | "onHide">,
  ): React.ReactNode {
    if (key === "recent-documents") {
      return (
        <DashboardWidgetFrame
          title="Recent documents"
          description="Your latest notes and captures."
          {...frame}
        >
          {recentDocuments.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-5 w-5/6" />
              <Skeleton className="h-5 w-2/3" />
            </div>
          ) : recentDocuments.isError ? (
            <div className="space-y-2">
              <p className="text-muted-foreground text-sm">
                Couldn&apos;t load documents. Is the API running?
              </p>
              <Button size="sm" variant="outline" onClick={() => void recentDocuments.refetch()}>
                Retry
              </Button>
            </div>
          ) : recentDocuments.data?.items?.length ? (
            <ul className="space-y-2">
              {recentDocuments.data.items.slice(0, 6).map((doc) => (
                <li key={doc.id} className="flex items-start justify-between gap-3">
                  <Link
                    href={`/documents/${doc.id}`}
                    className="hover:text-foreground text-sm leading-snug font-medium underline-offset-4 hover:underline"
                  >
                    {doc.title || "Untitled document"}
                  </Link>
                  <div className="text-muted-foreground shrink-0 text-xs">
                    {formatTimestamp(doc.created_at) ?? doc.day_bucket}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground text-sm">No documents yet.</p>
          )}

          <div>
            <Button asChild size="sm" variant="ghost">
              <Link href="/documents">Browse documents</Link>
            </Button>
          </div>
        </DashboardWidgetFrame>
      );
    }

    if (key === "company-research") {
      return (
        <DashboardWidgetFrame
          title="Company research"
          description="Recent briefs and executive summaries."
          {...frame}
        >
          {recentReports.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-5 w-4/5" />
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-5 w-3/4" />
            </div>
          ) : recentReports.isError ? (
            <div className="space-y-2">
              <p className="text-muted-foreground text-sm">
                Couldn&apos;t load reports. Is the API running?
              </p>
              <Button size="sm" variant="outline" onClick={() => void recentReports.refetch()}>
                Retry
              </Button>
            </div>
          ) : recentReports.data?.length ? (
            <ul className="space-y-2">
              {recentReports.data.slice(0, 6).map((report) => (
                <li key={report.id} className="space-y-1">
                  <div className="flex items-start justify-between gap-3">
                    <Link
                      href={`/company?reportId=${encodeURIComponent(report.id)}`}
                      className="hover:text-foreground text-sm leading-snug font-medium underline-offset-4 hover:underline"
                    >
                      {report.company}
                    </Link>
                    <div className="text-muted-foreground shrink-0 text-xs">
                      {formatTimestamp(report.updated_at ?? report.generated_at)}
                    </div>
                  </div>
                  {report.executive_summary ? (
                    <p className="text-muted-foreground line-clamp-2 text-sm">
                      {report.executive_summary}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground text-sm">No company reports yet.</p>
          )}

          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="ghost">
              <Link href="/company">Open company research</Link>
            </Button>
            <Badge variant="secondary">Citations</Badge>
          </div>
        </DashboardWidgetFrame>
      );
    }

    if (key === "threads") {
      return (
        <DashboardWidgetFrame
          title="Threads"
          description="Recent conversations and notes."
          {...frame}
        >
          {threads.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-5 w-5/6" />
              <Skeleton className="h-5 w-3/5" />
            </div>
          ) : threads.isError ? (
            <div className="space-y-2">
              <p className="text-muted-foreground text-sm">
                Couldn&apos;t load threads. Is the API running?
              </p>
              <Button size="sm" variant="outline" onClick={() => void threads.refetch()}>
                Retry
              </Button>
            </div>
          ) : sortedThreads.length ? (
            <ul className="space-y-2">
              {sortedThreads.map((thread) => (
                <li key={thread.id} className="flex items-start justify-between gap-3">
                  <Link
                    href={`/threads/${thread.id}`}
                    className="hover:text-foreground text-sm leading-snug font-medium underline-offset-4 hover:underline"
                  >
                    {thread.title || thread.kind || "Untitled thread"}
                  </Link>
                  <div className="text-muted-foreground shrink-0 text-xs">
                    {formatTimestamp(thread.updated_at ?? thread.created_at)}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground text-sm">No threads yet.</p>
          )}

          <div>
            <Button asChild size="sm" variant="ghost">
              <Link href="/threads">Open threads</Link>
            </Button>
          </div>
        </DashboardWidgetFrame>
      );
    }

    if (key === "follow-ups") {
      return (
        <DashboardWidgetFrame
          title="Follow-ups"
          description="Pending items and reminders."
          {...frame}
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant={
                followUpDueNowCount ? "destructive" : followUpOpenCount ? "secondary" : "outline"
              }
            >
              {followUpDueNowCount
                ? `${followUpDueNowCount} due`
                : followUpOpenCount
                  ? `${followUpOpenCount} open`
                  : "No follow-ups"}
            </Badge>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setFollowUpCenterOpen(true)}
            >
              Open center
            </Button>
            <Button asChild type="button" size="sm" variant="ghost">
              <Link href="/follow-ups">View all</Link>
            </Button>
          </div>

          {visibleFollowUps.length ? (
            <ul className="space-y-2">
              {visibleFollowUps.map((item) => (
                <li key={item.id} className="flex items-start justify-between gap-3">
                  <Link
                    href={`/follow-ups?focus=${encodeURIComponent(item.id)}`}
                    className="hover:text-foreground text-sm leading-snug font-medium underline-offset-4 hover:underline"
                  >
                    {item.title}
                  </Link>
                  <div className="text-muted-foreground shrink-0 text-xs">
                    {item.dueAt ? formatDueTimestamp(item.dueAt) : "—"}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground text-sm">Nothing pending right now.</p>
          )}
        </DashboardWidgetFrame>
      );
    }

    if (key === "templates") {
      return (
        <DashboardWidgetFrame
          title="Templates"
          description="Quick-start common workflows."
          {...frame}
        >
          <div className="grid gap-2 sm:grid-cols-2">
            {templates.map((t) => (
              <Button
                key={t.href}
                asChild
                variant="outline"
                className="h-auto justify-start p-3 text-left"
              >
                <Link href={t.href} className="space-y-1">
                  <div className="font-medium">{t.title}</div>
                  <div className="text-muted-foreground text-xs">{t.description}</div>
                </Link>
              </Button>
            ))}
          </div>
        </DashboardWidgetFrame>
      );
    }

    return null;
  }

  function setHidden(key: DashboardWidgetKey, hidden: boolean) {
    setLayout((prev) => {
      const nextHidden = new Set(prev.hidden);
      if (hidden) nextHidden.add(key);
      else nextHidden.delete(key);
      return { ...prev, hidden: nextHidden };
    });
  }

  function resetLayout() {
    setLayout(defaultDashboardLayout());
  }

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground text-sm">
            Jump back into recent work and start a new session quickly.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm">
            <Link href="/company">Research a company</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/rag">Ask Alfred</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/documents">Documents</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/tasks">Tasks</Link>
          </Button>
          <Button
            type="button"
            size="sm"
            variant={isEditing ? "secondary" : "outline"}
            onClick={() => setIsEditing((prev) => !prev)}
          >
            <LayoutDashboard className="mr-2 h-4 w-4" aria-hidden="true" />
            {isEditing ? "Done" : "Customize"}
          </Button>
          {isEditing ? (
            <>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button type="button" size="sm" variant="outline" disabled={!hiddenKeys.length}>
                    <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
                    Add widget
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {hiddenKeys.map((key) => (
                    <DropdownMenuItem key={key} onSelect={() => setHidden(key, false)}>
                      {widgetLabels[key]}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
              <Button type="button" size="sm" variant="ghost" onClick={resetLayout}>
                <RotateCcw className="mr-2 h-4 w-4" aria-hidden="true" />
                Reset
              </Button>
            </>
          ) : null}
        </div>
      </header>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={({ active, over }) => {
          if (!over) return;
          const activeId = active.id as DashboardWidgetKey;
          const overId = over.id as DashboardWidgetKey;
          if (activeId === overId) return;

          setLayout((prev) => {
            const from = prev.order.indexOf(activeId);
            const to = prev.order.indexOf(overId);
            if (from === -1 || to === -1) return prev;
            return { ...prev, order: arrayMove(prev.order, from, to) };
          });
        }}
      >
        <SortableContext items={visibleKeys} strategy={rectSortingStrategy}>
          <div className="grid gap-4 lg:grid-cols-3">
            {visibleKeys.map((key) => (
              <SortableWidget key={key} id={key} disabled={!isEditing}>
                {({ dragHandleProps }) => (
                  <div>
                    {renderWidget(key, {
                      isEditing,
                      dragHandleProps,
                      onHide: () => setHidden(key, true),
                    })}
                  </div>
                )}
              </SortableWidget>
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
}
