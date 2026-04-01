"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import {
  CheckCircle2,
  CircleAlert,
  Clock,
  Loader2,
  Trash2,
} from "lucide-react";

import { useTaskTracker } from "@/features/tasks/task-tracker-provider";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

const TWENTY_FOUR_HOURS_MS = 24 * 60 * 60 * 1000;

function formatElapsed(createdAt: string): string {
  const elapsed = Date.now() - new Date(createdAt).getTime();
  if (elapsed < 60_000) return "< 1m";
  if (elapsed < 3_600_000) return `${Math.floor(elapsed / 60_000)}m`;
  if (elapsed < 86_400_000) return `${Math.floor(elapsed / 3_600_000)}h`;
  return `${Math.floor(elapsed / 86_400_000)}d`;
}

function StatusBadge({ status }: { status: "running" | "completed" | "failed" }) {
  const styles = {
    running: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
    completed: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
    failed: "bg-red-500/15 text-red-600 dark:text-red-400",
  };

  const icons = {
    running: <Loader2 className="size-3 animate-spin" />,
    completed: <CheckCircle2 className="size-3" />,
    failed: <CircleAlert className="size-3" />,
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider",
        styles[status],
      )}
    >
      {icons[status]}
      {status}
    </span>
  );
}

export function TaskCenterSheet() {
  const router = useRouter();
  const {
    tasks,
    statusById,
    isTaskCenterOpen,
    setTaskCenterOpen,
    removeTask,
    clearCompleted,
  } = useTaskTracker();

  // Auto-purge completed tasks older than 24 hours on mount
  React.useEffect(() => {
    if (!isTaskCenterOpen) return;
    const now = Date.now();
    tasks.forEach((task) => {
      const status = statusById[task.id];
      if (
        status?.ready &&
        new Date(task.createdAt).getTime() < now - TWENTY_FOUR_HOURS_MS
      ) {
        removeTask(task.id);
      }
    });
    // Only run when the sheet opens
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isTaskCenterOpen]);

  const hasCompleted = tasks.some((t) => statusById[t.id]?.ready);

  return (
    <Sheet open={isTaskCenterOpen} onOpenChange={setTaskCenterOpen}>
      <SheetContent side="right" className="w-[380px] sm:max-w-[380px]">
        <SheetHeader>
          <SheetTitle className="text-sm tracking-wide">
            Task Center
          </SheetTitle>
          <SheetDescription className="text-xs text-[var(--alfred-text-tertiary)]">
            Background tasks and workflows
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-4">
          {tasks.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Clock className="size-8 text-[var(--alfred-text-tertiary)] opacity-40" />
              <p className="mt-3 text-sm text-muted-foreground">
                No background tasks
              </p>
              <p className="mt-1 text-xs text-[var(--alfred-text-tertiary)]">
                Triggered workflows will appear here
              </p>
            </div>
          ) : (
            <ul className="space-y-2">
              {tasks.map((task) => {
                const status = statusById[task.id];
                const taskStatus: "running" | "completed" | "failed" = status
                  ?.ready
                  ? status.successful
                    ? "completed"
                    : "failed"
                  : "running";

                return (
                  <li
                    key={task.id}
                    className="group flex items-start gap-3 rounded-lg border px-3 py-2.5 transition-colors hover:bg-[var(--alfred-accent-subtle)]"
                  >
                    <div className="flex-1 min-w-0">
                      <button
                        type="button"
                        className="text-left text-sm font-medium leading-tight truncate block w-full hover:underline"
                        onClick={() => {
                          if (task.href) {
                            router.push(task.href);
                            setTaskCenterOpen(false);
                          }
                        }}
                      >
                        {task.label}
                      </button>
                      <div className="mt-1.5 flex items-center gap-2">
                        <StatusBadge status={taskStatus} />
                        <span className="text-[10px] text-[var(--alfred-text-tertiary)]">
                          {formatElapsed(task.createdAt)}
                        </span>
                      </div>
                      {status?.failed && status.error && (
                        <p className="mt-1 text-[11px] text-red-500 line-clamp-2">
                          {status.error}
                        </p>
                      )}
                    </div>
                    <button
                      type="button"
                      className="mt-1 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
                      onClick={() => removeTask(task.id)}
                      aria-label={`Remove ${task.label}`}
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {hasCompleted && (
          <div className="border-t px-4 py-3">
            <Button
              variant="ghost"
              size="sm"
              className="w-full text-xs text-muted-foreground"
              onClick={clearCompleted}
            >
              Clear completed
            </Button>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
