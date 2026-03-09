"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  Bell,
  CheckCircle2,
  CircleDashed,
  ListChecks,
  Trash2,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";
import { formatRelativeTimestamp } from "@/lib/utils/date-format";
import { useFollowUps } from "@/features/follow-ups/follow-up-provider";
import { useTaskTracker } from "@/features/tasks/task-tracker-provider";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";

function TaskStatusPill({
  status,
}: {
  status?: { status: string; ready: boolean; successful: boolean; failed: boolean };
}) {
  if (!status) {
    return (
      <span className="text-muted-foreground inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs">
        <CircleDashed className="h-3 w-3" aria-hidden="true" />
        Unknown
      </span>
    );
  }

  if (!status.ready) {
    return (
      <span className="text-muted-foreground inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs">
        <CircleDashed className="h-3 w-3" aria-hidden="true" />
        {status.status}
      </span>
    );
  }

  if (status.failed) {
    return (
      <span className="border-destructive/30 bg-destructive/5 text-destructive inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs">
        <XCircle className="h-3 w-3" aria-hidden="true" />
        Failed
      </span>
    );
  }

  if (status.successful) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs">
        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
        Complete
      </span>
    );
  }

  return (
    <span className="text-muted-foreground inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs">
      {status.status}
    </span>
  );
}

export function TaskCenterSheet() {
  const router = useRouter();
  const { addFollowUp, setFollowUpCenterOpen } = useFollowUps();
  const {
    tasks,
    statusById,
    activeCount,
    isOnline,
    isTaskCenterOpen,
    setTaskCenterOpen,
    trackTask,
    removeTask,
    clearCompleted,
  } = useTaskTracker();

  const [manualTaskId, setManualTaskId] = React.useState("");

  const hasTasks = tasks.length > 0;
  const completedCount = React.useMemo(() => {
    return tasks.reduce((count, task) => (statusById[task.id]?.ready ? count + 1 : count), 0);
  }, [statusById, tasks]);

  return (
    <Sheet open={isTaskCenterOpen} onOpenChange={setTaskCenterOpen}>
      <SheetContent side="right" className="w-[420px] sm:max-w-[520px]">
        <SheetHeader className="space-y-2">
          <div className="flex items-start justify-between gap-3 pr-8">
            <div className="space-y-1">
              <SheetTitle className="flex items-center gap-2">
                <ListChecks className="h-4 w-4" aria-hidden="true" />
                Task Center
              </SheetTitle>
              <p className="text-muted-foreground text-sm">
                Track background jobs and jump back into results.
              </p>
            </div>
            <div className="flex flex-col items-end gap-1">
              <Badge variant={activeCount ? "secondary" : "outline"}>
                {activeCount ? `${activeCount} active` : "No active tasks"}
              </Badge>
              <span
                className={cn("text-xs", isOnline ? "text-muted-foreground" : "text-destructive")}
              >
                {isOnline ? "Online" : "Offline"}
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Input
              value={manualTaskId}
              onChange={(event) => setManualTaskId(event.target.value)}
              placeholder="Paste a task id to track…"
            />
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                const trimmed = manualTaskId.trim();
                if (!trimmed) return;
                trackTask({ id: trimmed, label: `Task ${trimmed.slice(0, 8)}`, source: "generic" });
                setManualTaskId("");
              }}
            >
              Track
            </Button>
          </div>

          <div className="flex items-center justify-end">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={!completedCount}
              onClick={clearCompleted}
            >
              <Trash2 className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
              Clear completed
            </Button>
          </div>
        </SheetHeader>

        <Separator />

        {!hasTasks ? (
          <EmptyState
            icon={ListChecks}
            title="No tracked tasks yet"
            description="Start a Company Research or Interview Prep run in background and it will show up here."
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Button asChild type="button" variant="outline" size="sm">
                  <Link href="/company">Company</Link>
                </Button>
                <Button asChild type="button" variant="outline" size="sm">
                  <Link href="/interview-prep">Interview Prep</Link>
                </Button>
              </div>
            }
          />
        ) : (
          <div className="min-h-0 flex-1 overflow-auto">
            <div className="space-y-3">
              {tasks.map((task) => {
                const status = statusById[task.id];
                const isLoading = isOnline && !status;

                return (
                  <div key={task.id} className="bg-background rounded-lg border p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate text-sm font-medium">{task.label}</p>
                          <TaskStatusPill status={status} />
                        </div>
                        <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
                          <span className="font-mono">{task.id}</span>
                          <span>•</span>
                          <span>{formatRelativeTimestamp(task.createdAt)}</span>
                        </div>

                        {isLoading ? (
                          <div className="space-y-2 pt-2">
                            <Skeleton className="h-3 w-48" />
                            <Skeleton className="h-3 w-32" />
                          </div>
                        ) : status?.failed && status.error ? (
                          <Alert variant="destructive" className="mt-2 px-3 py-2">
                            <AlertDescription className="text-destructive">
                              {status.error}
                            </AlertDescription>
                          </Alert>
                        ) : null}
                      </div>

                      <div className="flex shrink-0 items-center gap-1">
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            setTaskCenterOpen(false);
                            router.push(
                              task.href ?? "/dashboard",
                            );
                          }}
                        >
                          View
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label="Create follow-up"
                          onClick={() => {
                            const dueAt = new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString();
                            const href =
                              task.href ?? "/dashboard";

                            const created = addFollowUp({
                              title: `Review: ${task.label}`,
                              dueAt,
                              href,
                              source: "task",
                              templateLabel: "From Task Center",
                              meta: {
                                task_id: task.id,
                                task_source: task.source,
                                task_label: task.label,
                              },
                            });

                            if (!created) return;
                            toast.success("Follow-up created.");
                            setFollowUpCenterOpen(true);
                          }}
                        >
                          <Bell className="h-4 w-4" aria-hidden="true" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label="Remove task"
                          onClick={() => removeTask(task.id)}
                        >
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

export function TaskCenterTrigger({
  className,
  variant = "icon",
}: {
  className?: string;
  variant?: "icon" | "button";
}) {
  const { activeCount, setTaskCenterOpen } = useTaskTracker();
  const [hasMounted, setHasMounted] = React.useState(false);

  React.useEffect(() => {
    queueMicrotask(() => setHasMounted(true));
  }, []);

  if (variant === "button") {
    return (
      <Button
        type="button"
        variant="outline"
        size="sm"
        className={className}
        onClick={() => setTaskCenterOpen(true)}
      >
        <ListChecks className="mr-2 h-4 w-4" aria-hidden="true" />
        Tasks
        {hasMounted && activeCount ? (
          <span className="bg-muted text-muted-foreground ml-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-xs">
            {activeCount}
          </span>
        ) : null}
      </Button>
    );
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className={className}
      aria-label="Open task center"
      onClick={() => setTaskCenterOpen(true)}
    >
      <span className="relative">
        <ListChecks className="h-4 w-4" aria-hidden="true" />
        {hasMounted && activeCount ? (
          <span className="bg-destructive text-destructive-foreground absolute -top-1.5 -right-1.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-medium">
            {activeCount}
          </span>
        ) : null}
      </span>
    </Button>
  );
}
