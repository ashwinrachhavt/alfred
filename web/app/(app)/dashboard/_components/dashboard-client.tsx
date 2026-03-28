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

import { useRecentResearchReports } from "@/features/research/queries";
import { useRecentDocuments } from "@/features/documents/queries";
import { useShellStore } from "@/lib/stores/shell-store";
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
import { formatDueTimestamp } from "@/lib/utils/date-format";
import {
  defaultDashboardLayout,
  loadDashboardLayout,
  saveDashboardLayout,
  type DashboardWidgetKey,
} from "@/features/dashboard/dashboard-layout";

/** Local alias so existing call-sites that pass `string | null | undefined` keep working. */
const formatTimestamp = (value: string | null | undefined): string | null =>
  formatDueTimestamp(value ?? undefined);

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
  const recentReports = useRecentResearchReports(6);
  const { setAiPanelOpen } = useShellStore();

  const widgetLabels = React.useMemo<Record<DashboardWidgetKey, string>>(
    () => ({
      "recent-documents": "Recent documents",
      "company-research": "Deep research",

      templates: "Templates",
    }),
    [],
  );

  const [isEditing, setIsEditing] = React.useState(false);
  const [layout, setLayout] = React.useState(() =>
    loadDashboardLayout([
      "recent-documents",
      "company-research",
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


  const templates: Array<{ title: string; description: string; href: string }> = [
    {
      title: "Deep research",
      description: "Generate a brief with citations.",
      href: "/research",
    },
    {
      title: "System design session",
      description: "Start with a pre-filled problem statement.",
      href: "/system-design?problemStatement=Design%20a%20rate%20limiter%20for%20an%20API",
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
              <Link href="/library">Browse documents</Link>
            </Button>
          </div>
        </DashboardWidgetFrame>
      );
    }

    if (key === "company-research") {
      return (
        <DashboardWidgetFrame
          title="Deep research"
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
                      href={`/research?reportId=${encodeURIComponent(report.id)}`}
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
              <Link href="/research">Open company research</Link>
            </Button>
            <Badge variant="secondary">Citations</Badge>
          </div>
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
            <Link href="/research">Research a company</Link>
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setAiPanelOpen(true)}
          >
            Ask Alfred
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/library">Library</Link>
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
