"use client";

import * as React from "react";
import Link from "next/link";

import { Bell, CheckCircle2, Clock, ExternalLink, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";
import { useFollowUps } from "@/features/follow-ups/follow-up-provider";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

type FollowUpsClientProps = {
  initialTitle: string;
  initialDueAt: string;
  initialDueInMinutes: string;
  initialHref: string;
  focusId: string;
};

function toLocalDateTimeInput(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.valueOf())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

function fromLocalDateTimeInput(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const date = new Date(trimmed);
  if (Number.isNaN(date.valueOf())) return null;
  return date.toISOString();
}

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

function dueVariant(dueAt: string | undefined): "secondary" | "default" | "destructive" {
  if (!dueAt) return "secondary";
  const dueMs = Date.parse(dueAt);
  if (Number.isNaN(dueMs)) return "secondary";
  const delta = dueMs - Date.now();
  if (delta <= 0) return "destructive";
  if (delta <= 2 * 60 * 60 * 1000) return "default";
  return "secondary";
}

function isSnoozedUntilFuture(value: string | undefined): boolean {
  if (!value) return false;
  const until = Date.parse(value);
  if (Number.isNaN(until)) return false;
  return until > Date.now();
}

export function FollowUpsClient({
  initialTitle,
  initialDueAt,
  initialDueInMinutes,
  initialHref,
  focusId,
}: FollowUpsClientProps) {
  const { items, addFollowUp, markDone, snooze, removeFollowUp, clearCompleted, updateFollowUp } =
    useFollowUps();

  const [title, setTitle] = React.useState(initialTitle);
  const [href, setHref] = React.useState(initialHref);
  const [notes, setNotes] = React.useState("");
  const [dueAtLocal, setDueAtLocal] = React.useState("");
  const [filter, setFilter] = React.useState("");

  const focusRef = React.useRef<string>(focusId);
  const itemRefs = React.useRef<Record<string, HTMLDivElement | null>>({});

  React.useEffect(() => {
    const trimmedFocus = focusRef.current.trim();
    if (!trimmedFocus) return;
    const target = itemRefs.current[trimmedFocus];
    if (!target) return;
    target.scrollIntoView({ block: "center", behavior: "smooth" });
    target.classList.add("ring-2", "ring-ring");
    window.setTimeout(() => target.classList.remove("ring-2", "ring-ring"), 1800);
    focusRef.current = "";
  }, [items]);

  React.useEffect(() => {
    const dueAt = initialDueAt.trim();
    if (dueAt) {
      const normalized = new Date(dueAt);
      if (!Number.isNaN(normalized.valueOf())) {
        setDueAtLocal(toLocalDateTimeInput(normalized.toISOString()));
        return;
      }
    }

    const minutes = Number(initialDueInMinutes);
    if (Number.isFinite(minutes) && minutes > 0) {
      const due = new Date(Date.now() + minutes * 60_000).toISOString();
      setDueAtLocal(toLocalDateTimeInput(due));
    }
  }, [initialDueAt, initialDueInMinutes]);

  const openItems = React.useMemo(() => items.filter((item) => !item.completedAt), [items]);
  const doneItems = React.useMemo(() => items.filter((item) => item.completedAt), [items]);

  const filteredOpen = React.useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return openItems;
    return openItems.filter((item) => item.title.toLowerCase().includes(q));
  }, [filter, openItems]);

  const filteredDone = React.useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return doneItems;
    return doneItems.filter((item) => item.title.toLowerCase().includes(q));
  }, [doneItems, filter]);

  const create = () => {
    const trimmed = title.trim();
    if (!trimmed) {
      toast.error("Add a title first.");
      return;
    }

    const created = addFollowUp({
      title: trimmed,
      href,
      notes,
      dueAt: fromLocalDateTimeInput(dueAtLocal),
      source: "manual",
    });
    if (!created) return;

    setTitle("");
    setHref("");
    setNotes("");
    setDueAtLocal("");
    toast.success("Follow-up added.");
  };

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Follow-ups</h1>
          <p className="text-muted-foreground text-sm">
            A lightweight reminder list — snooze, mark done, and keep moving.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" onClick={clearCompleted}>
            <Trash2 className="mr-2 h-4 w-4" aria-hidden="true" />
            Clear done
          </Button>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[1fr_420px]">
        <Card>
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <CardTitle>All follow-ups</CardTitle>
              <p className="text-muted-foreground text-sm">
                {openItems.length} open • {doneItems.length} done
              </p>
            </div>
            <div className="w-full sm:w-72">
              <div className="relative">
                <Search className="text-muted-foreground absolute top-2.5 left-2 h-4 w-4" />
                <Input
                  className="pl-8"
                  placeholder="Filter…"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="open">
              <TabsList>
                <TabsTrigger value="open">Open</TabsTrigger>
                <TabsTrigger value="done">Done</TabsTrigger>
              </TabsList>

              <TabsContent value="open" className="pt-4">
                {filteredOpen.length ? (
                  <div className="divide-border divide-y rounded-md border">
                    {filteredOpen.map((item) => {
                      const snoozed = isSnoozedUntilFuture(item.snoozedUntil);
                      const dueLabel = item.dueAt ? formatDue(item.dueAt) : null;
                      const variant = dueVariant(item.dueAt);

                      return (
                        <div
                          key={item.id}
                          ref={(node) => {
                            itemRefs.current[item.id] = node;
                          }}
                          className={cn("p-4 transition-colors", snoozed ? "opacity-70" : null)}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="min-w-0 space-y-2">
                              <p className="truncate font-medium">{item.title}</p>

                              <div className="flex flex-wrap items-center gap-2">
                                {item.dueAt ? (
                                  <Badge variant={variant} className="gap-1">
                                    <Clock className="h-3 w-3" aria-hidden="true" />
                                    {variant === "destructive" ? "Overdue" : "Due"}
                                    {dueLabel ? `: ${dueLabel}` : null}
                                  </Badge>
                                ) : (
                                  <Badge variant="secondary">No due date</Badge>
                                )}
                                {snoozed ? <Badge variant="outline">Snoozed</Badge> : null}
                                {item.source ? (
                                  <Badge variant="outline">{item.source}</Badge>
                                ) : null}
                              </div>

                              {item.notes ? (
                                <p className="text-muted-foreground line-clamp-2 text-sm">
                                  {item.notes}
                                </p>
                              ) : null}

                              {item.href ? (
                                <Button asChild size="sm" variant="ghost">
                                  {item.href.startsWith("/") ? (
                                    <Link href={item.href}>
                                      Open link
                                      <ExternalLink
                                        className="ml-1 h-3.5 w-3.5"
                                        aria-hidden="true"
                                      />
                                    </Link>
                                  ) : (
                                    <a href={item.href} target="_blank" rel="noreferrer">
                                      Open link
                                      <ExternalLink
                                        className="ml-1 h-3.5 w-3.5"
                                        aria-hidden="true"
                                      />
                                    </a>
                                  )}
                                </Button>
                              ) : null}
                            </div>

                            <div className="flex shrink-0 flex-col items-end gap-2">
                              <Button type="button" size="sm" onClick={() => markDone(item.id)}>
                                <CheckCircle2 className="mr-2 h-4 w-4" aria-hidden="true" />
                                Done
                              </Button>
                              <div className="flex flex-wrap justify-end gap-2">
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => snooze(item.id, 60)}
                                >
                                  Snooze 1h
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => removeFollowUp(item.id)}
                                >
                                  Remove
                                </Button>
                              </div>
                              {snoozed ? (
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => updateFollowUp(item.id, { snoozedUntil: null })}
                                >
                                  Unsnooze
                                </Button>
                              ) : null}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="pt-6">
                    <EmptyState
                      icon={Bell}
                      title={openItems.length ? "No matches" : "No follow-ups yet"}
                      description={
                        openItems.length ? "Try a different filter." : "Add one on the right."
                      }
                    />
                  </div>
                )}
              </TabsContent>

              <TabsContent value="done" className="pt-4">
                {filteredDone.length ? (
                  <div className="divide-border divide-y rounded-md border">
                    {filteredDone.map((item) => (
                      <div key={item.id} className="p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 space-y-1">
                            <p className="truncate font-medium">{item.title}</p>
                            <p className="text-muted-foreground text-xs">
                              Completed {item.completedAt ? formatDue(item.completedAt) : "—"}
                            </p>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => removeFollowUp(item.id)}
                          >
                            Remove
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="pt-6">
                    <EmptyState
                      icon={CheckCircle2}
                      title={doneItems.length ? "No matches" : "No completed follow-ups"}
                      description={
                        doneItems.length
                          ? "Try a different filter."
                          : "Mark items done to see them here."
                      }
                    />
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Add follow-up</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="fuTitle">Title</Label>
                <Input
                  id="fuTitle"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Send the recap email"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="fuDue">Due (optional)</Label>
                <Input
                  id="fuDue"
                  type="datetime-local"
                  value={dueAtLocal}
                  onChange={(e) => setDueAtLocal(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="fuHref">Link (optional)</Label>
                <Input
                  id="fuHref"
                  value={href}
                  onChange={(e) => setHref(e.target.value)}
                  placeholder="https://… or /threads/…"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="fuNotes">Notes (optional)</Label>
                <Textarea
                  id="fuNotes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Context, checklist, next step…"
                  rows={4}
                />
              </div>

              <Separator />

              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" onClick={create}>
                  Add follow-up
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setTitle("");
                    setHref("");
                    setNotes("");
                    setDueAtLocal("");
                  }}
                >
                  Reset
                </Button>
              </div>

              <p className="text-muted-foreground text-xs">
                Tip: due follow-ups trigger a toast reminder (and show in the follow-up center).
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
