"use client";

import * as React from "react";

import { Bell, CheckCircle2, Clock, Trash2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { useFollowUps } from "@/features/follow-ups/follow-up-provider";
import { useNowMs } from "@/hooks/use-now";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";

function formatDue(value: string): string | null {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return null;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function formatSnoozeUntil(value: string): string | null {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return null;
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(date);
}

function isSnoozedUntilFuture(value: string | undefined, nowMs: number): boolean {
  if (!value) return false;
  const until = Date.parse(value);
  if (Number.isNaN(until)) return false;
  return until > nowMs;
}

function dueBadgeVariant(
  dueAt: string | undefined,
  nowMs: number,
): "default" | "secondary" | "destructive" {
  if (!dueAt) return "secondary";
  const dueMs = Date.parse(dueAt);
  if (Number.isNaN(dueMs)) return "secondary";
  const delta = dueMs - nowMs;
  if (delta <= 0) return "destructive";
  if (delta <= 2 * 60 * 60 * 1000) return "default";
  return "secondary";
}

function buildDueAtFromOffset(minutes: number): string {
  const mins = Math.max(5, Math.min(14 * 24 * 60, minutes));
  return new Date(Date.now() + mins * 60_000).toISOString();
}

export function FollowUpCenterSheet() {
  const {
    items,
    openCount,
    dueNowCount,
    isFollowUpCenterOpen,
    setFollowUpCenterOpen,
    addFollowUp,
    markDone,
    snooze,
    removeFollowUp,
    clearCompleted,
  } = useFollowUps();
  const nowMs = useNowMs(30_000);

  const [title, setTitle] = React.useState("");
  const [duePreset, setDuePreset] = React.useState<"none" | "1h" | "tomorrow" | "1w">("tomorrow");

  const openItems = React.useMemo(() => items.filter((item) => !item.completedAt), [items]);

  const sortedOpenItems = React.useMemo(() => {
    return openItems.slice().sort((a, b) => {
      const aSnoozed = isSnoozedUntilFuture(a.snoozedUntil, nowMs);
      const bSnoozed = isSnoozedUntilFuture(b.snoozedUntil, nowMs);
      if (aSnoozed !== bSnoozed) return aSnoozed ? 1 : -1;

      const aDue = a.dueAt ? Date.parse(a.dueAt) : Number.POSITIVE_INFINITY;
      const bDue = b.dueAt ? Date.parse(b.dueAt) : Number.POSITIVE_INFINITY;

      const aOverdue = Number.isFinite(aDue) && aDue <= nowMs;
      const bOverdue = Number.isFinite(bDue) && bDue <= nowMs;
      if (aOverdue !== bOverdue) return aOverdue ? -1 : 1;

      if (aDue !== bDue) return aDue - bDue;
      return b.createdAt.localeCompare(a.createdAt);
    });
  }, [nowMs, openItems]);

  const completedCount = React.useMemo(
    () => items.reduce((count, item) => (item.completedAt ? count + 1 : count), 0),
    [items],
  );

  const hasAny = items.length > 0;

  const create = () => {
    const trimmed = title.trim();
    if (!trimmed) return;

    const dueAt =
      duePreset === "none"
        ? null
        : duePreset === "1h"
          ? buildDueAtFromOffset(60)
          : duePreset === "1w"
            ? buildDueAtFromOffset(7 * 24 * 60)
            : buildDueAtFromOffset(24 * 60);

    const created = addFollowUp({
      title: trimmed,
      dueAt,
      source: "manual",
    });
    if (!created) return;
    setTitle("");
  };

  return (
    <Sheet open={isFollowUpCenterOpen} onOpenChange={setFollowUpCenterOpen}>
      <SheetContent side="right" className="w-[420px] sm:max-w-[520px]">
        <SheetHeader className="space-y-2">
          <div className="flex items-start justify-between gap-3 pr-8">
            <div className="space-y-1">
              <SheetTitle className="flex items-center gap-2">
                <Bell className="h-4 w-4" aria-hidden="true" />
                Follow-ups
              </SheetTitle>
              <p className="text-muted-foreground text-sm">
                Keep track of pending items and get reminders when they’re due.
              </p>
            </div>
            <div className="flex flex-col items-end gap-1">
              <Badge variant={dueNowCount ? "destructive" : openCount ? "secondary" : "outline"}>
                {dueNowCount
                  ? `${dueNowCount} due`
                  : openCount
                    ? `${openCount} open`
                    : "No follow-ups"}
              </Badge>
            </div>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Add a follow-up…"
              onKeyDown={(event) => {
                if (event.key !== "Enter") return;
                event.preventDefault();
                create();
              }}
            />
            <div className="flex gap-2">
              <select
                className="bg-background h-10 rounded-md border px-2 text-sm"
                value={duePreset}
                onChange={(event) => setDuePreset(event.target.value as typeof duePreset)}
                aria-label="Due preset"
              >
                <option value="none">No due</option>
                <option value="1h">In 1h</option>
                <option value="tomorrow">Tomorrow</option>
                <option value="1w">In 1 week</option>
              </select>
              <Button type="button" variant="secondary" onClick={create}>
                Add
              </Button>
            </div>
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
              Clear done
            </Button>
          </div>
        </SheetHeader>

        <Separator />

        {!hasAny ? (
          <EmptyState
            icon={Bell}
            title="No follow-ups yet"
            description="Create one, snooze it, and Alfred will remind you when it's due."
          />
        ) : (
          <div className="min-h-0 flex-1 overflow-auto">
            <div className="space-y-3">
              {sortedOpenItems.map((item) => {
                const snoozed = isSnoozedUntilFuture(item.snoozedUntil, nowMs);
                const dueLabel = item.dueAt ? formatDue(item.dueAt) : null;
                const snoozeLabel = item.snoozedUntil ? formatSnoozeUntil(item.snoozedUntil) : null;
                const variant = dueBadgeVariant(item.dueAt, nowMs);

                return (
                  <div
                    key={item.id}
                    className={cn(
                      "bg-background rounded-lg border p-3 transition-colors",
                      snoozed ? "opacity-75" : null,
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 space-y-1">
                        <p className="truncate text-sm font-medium">{item.title}</p>
                        <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
                          {item.dueAt ? (
                            <Badge variant={variant} className="gap-1">
                              <Clock className="h-3 w-3" aria-hidden="true" />
                              {variant === "destructive" ? "Overdue" : "Due"}
                              {dueLabel ? `: ${dueLabel}` : null}
                            </Badge>
                          ) : (
                            <Badge variant="secondary">No due date</Badge>
                          )}
                          {snoozed && snoozeLabel ? (
                            <Badge variant="outline">Snoozed until {snoozeLabel}</Badge>
                          ) : null}
                        </div>
                      </div>

                      <div className="flex shrink-0 items-center gap-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label="Mark done"
                          onClick={() => markDone(item.id)}
                        >
                          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => snooze(item.id, 60)}
                        >
                          Snooze
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label="Remove follow-up"
                          onClick={() => removeFollowUp(item.id)}
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

export function FollowUpCenterTrigger({
  className,
  variant = "icon",
}: {
  className?: string;
  variant?: "icon" | "button";
}) {
  const { openCount, dueNowCount, setFollowUpCenterOpen } = useFollowUps();
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
        onClick={() => setFollowUpCenterOpen(true)}
      >
        <Bell className="mr-2 h-4 w-4" aria-hidden="true" />
        Follow-ups
        {hasMounted && dueNowCount ? (
          <span className="bg-destructive text-destructive-foreground ml-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-xs">
            {dueNowCount}
          </span>
        ) : hasMounted && openCount ? (
          <span className="bg-muted text-muted-foreground ml-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-xs">
            {openCount}
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
      aria-label="Open follow-up center"
      onClick={() => setFollowUpCenterOpen(true)}
    >
      <span className="relative">
        <Bell className="h-4 w-4" aria-hidden="true" />
        {hasMounted && dueNowCount ? (
          <span className="bg-destructive text-destructive-foreground absolute -top-1.5 -right-1.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-medium">
            {dueNowCount}
          </span>
        ) : null}
      </span>
    </Button>
  );
}
