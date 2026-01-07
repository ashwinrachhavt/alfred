"use client";

import Link from "next/link";

import { useMemo, useState } from "react";

import { MessageSquareText, Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api/client";
import type { Thread } from "@/lib/api/types/threads";
import { useCreateThread } from "@/features/threads/mutations";
import { useThreads } from "@/features/threads/queries";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

const EMPTY_THREADS: Thread[] = [];

function formatMaybeDate(raw?: string | null): string {
  if (!raw) return "—";
  const maybeNumber = Number(raw);
  if (!Number.isNaN(maybeNumber) && Number.isFinite(maybeNumber)) {
    const date = new Date(maybeNumber);
    if (!Number.isNaN(date.getTime())) return date.toLocaleString();
  }
  const date = new Date(raw);
  if (!Number.isNaN(date.getTime())) return date.toLocaleString();
  return raw;
}

function threadTitle(thread: Thread): string {
  const title = thread.title?.trim();
  if (title) return title;
  return `Thread ${thread.id.slice(0, 8)}`;
}

function formatErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

export function ThreadsClient() {
  const threadsQuery = useThreads();
  const createThreadMutation = useCreateThread();

  const [title, setTitle] = useState("");
  const [filter, setFilter] = useState("");

  const threads = threadsQuery.data ?? EMPTY_THREADS;

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return threads;
    return threads.filter((thread) => threadTitle(thread).toLowerCase().includes(q));
  }, [filter, threads]);

  async function onCreateThread() {
    const nextTitle = title.trim();
    try {
      const created = await createThreadMutation.mutateAsync({ title: nextTitle || null });
      setTitle("");
      toast.success("Thread created");
      // Navigate optimistically via Link (user can click), but also keep list fresh.
      void threadsQuery.refetch();
      const createdTitle = threadTitle(created);
      toast.message(createdTitle, { description: "Open the thread to start appending messages." });
    } catch (err) {
      toast.error("Could not create thread", { description: formatErrorMessage(err) });
    }
  }

  const errorMessage = threadsQuery.isError ? formatErrorMessage(threadsQuery.error) : null;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Threads</h1>
        <p className="text-muted-foreground">
          Persistent conversations and notes. Used by interview prep to store request/response
          history.
        </p>
      </header>

      {errorMessage ? (
        <Alert variant="destructive">
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Create thread</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="threadTitle">Title (optional)</Label>
            <Input
              id="threadTitle"
              placeholder="e.g. Interview Prep — Stripe"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key !== "Enter") return;
                e.preventDefault();
                void onCreateThread();
              }}
            />
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              onClick={() => void onCreateThread()}
              disabled={createThreadMutation.isPending}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              Create
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => void threadsQuery.refetch()}
              disabled={threadsQuery.isFetching}
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Refresh
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <CardTitle>All threads</CardTitle>
            <p className="text-muted-foreground text-sm">
              {threadsQuery.isLoading ? "Loading…" : `${threads.length} total`}
            </p>
          </div>
          <div className="w-full sm:w-72">
            <Input
              placeholder="Filter…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
        </CardHeader>
        <CardContent>
          {threadsQuery.isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : filtered.length ? (
            <div className="divide-border divide-y rounded-md border">
              {filtered.map((thread) => (
                <Link
                  key={thread.id}
                  href={`/threads/${thread.id}`}
                  className="hover:bg-muted/40 flex items-start justify-between gap-4 p-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <MessageSquareText className="text-muted-foreground h-4 w-4" />
                      <p className="font-medium">{threadTitle(thread)}</p>
                    </div>
                    <p className="text-muted-foreground text-xs">
                      Updated: {formatMaybeDate(thread.updated_at ?? thread.created_at)}
                    </p>
                  </div>
                  <Badge variant="outline" className="shrink-0">
                    {thread.id.slice(0, 8)}
                  </Badge>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              title={threads.length ? "No matches" : "No threads yet"}
              description={
                threads.length ? "Try a different filter." : "Create a thread to begin."
              }
              icon={MessageSquareText}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
