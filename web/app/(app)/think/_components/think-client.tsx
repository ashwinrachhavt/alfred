"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import {
  Brain,
  Loader2,
  Pin,
  Plus,
  Search,
} from "lucide-react";
import { toast } from "sonner";

import type { ThinkingSessionSummary } from "@/lib/api/types/thinking";
import { useCreateThinkingSession } from "@/features/thinking/mutations";
import { useThinkingSessions } from "@/features/thinking/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const statusColors: Record<string, string> = {
  draft: "bg-yellow-500/10 text-yellow-700 dark:text-yellow-400",
  published: "bg-green-500/10 text-green-700 dark:text-green-400",
  archived: "bg-muted text-muted-foreground",
};

// ---------------------------------------------------------------------------
// Session List Item
// ---------------------------------------------------------------------------

function SessionListItem({
  session,
  isActive,
  onClick,
}: {
  session: ThinkingSessionSummary;
  isActive: boolean;
  onClick: () => void;
}) {
  const label = session.title || session.topic || "Untitled session";

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full rounded-lg border px-3 py-3 text-left transition-colors",
        isActive
          ? "border-primary/30 bg-primary/5"
          : "border-transparent hover:bg-muted/50",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5">
          {session.pinned ? (
            <Pin className="h-3 w-3 shrink-0 text-[var(--alfred-accent)]" />
          ) : null}
          <h3 className="truncate text-sm font-medium leading-snug">{label}</h3>
        </div>
        <span className="text-muted-foreground mt-0.5 shrink-0 text-[11px]">
          {formatRelativeDate(session.updated_at)}
        </span>
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        <Badge
          variant="outline"
          className={cn("text-[10px]", statusColors[session.status])}
        >
          {session.status}
        </Badge>
        <span className="text-muted-foreground text-[11px]">
          {session.block_count} block{session.block_count === 1 ? "" : "s"}
        </span>
        {session.tags.length > 0 ? (
          <span className="text-muted-foreground truncate text-[11px]">
            {session.tags.slice(0, 2).join(", ")}
          </span>
        ) : null}
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Session Thread List (left panel)
// ---------------------------------------------------------------------------

function SessionThreadList() {
  const router = useRouter();
  const sessionsQuery = useThinkingSessions();
  const sessions = sessionsQuery.data ?? [];
  const [search, setSearch] = useState("");
  const createSession = useCreateThinkingSession();

  const sorted = useMemo(() => {
    const filtered = search.trim()
      ? sessions.filter((s) => {
          const q = search.toLowerCase();
          const label = (s.title ?? s.topic ?? "").toLowerCase();
          const tags = s.tags.join(" ").toLowerCase();
          return label.includes(q) || tags.includes(q);
        })
      : sessions;

    return [...filtered].sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
    });
  }, [sessions, search]);

  const handleNew = async () => {
    try {
      const session = await createSession.mutateAsync({});
      router.push(`/think/${session.id}`);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to create session.",
      );
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <h2 className="font-serif text-lg tracking-tight">Think</h2>
        <Button
          size="sm"
          variant="ghost"
          onClick={handleNew}
          disabled={createSession.isPending}
        >
          {createSession.isPending ? (
            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Plus className="mr-1 h-3.5 w-3.5" />
          )}
          New
        </Button>
      </div>

      <div className="px-4 pb-2">
        <div className="relative">
          <Search className="text-muted-foreground absolute left-2.5 top-2.5 h-3.5 w-3.5" />
          <Input
            placeholder="Search sessions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 pl-8 text-xs"
          />
        </div>
      </div>

      <Separator />

      <div className="flex-1 space-y-1 overflow-y-auto px-3 py-2">
        {sessionsQuery.isLoading ? (
          <div className="space-y-3 px-1 py-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="space-y-1.5">
                <div className="bg-muted h-4 w-3/4 animate-pulse rounded" />
                <div className="bg-muted h-3 w-full animate-pulse rounded" />
              </div>
            ))}
          </div>
        ) : sorted.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Brain className="text-muted-foreground/50 mb-3 h-8 w-8" />
            <p className="text-muted-foreground text-sm">
              {search ? "No matching sessions" : "No thinking sessions yet"}
            </p>
            <p className="text-muted-foreground mt-1 text-xs">
              {search
                ? "Try a different search term"
                : "Create your first session to start thinking"}
            </p>
          </div>
        ) : (
          sorted.map((session) => (
            <SessionListItem
              key={session.id}
              session={session}
              isActive={false}
              onClick={() => router.push(`/think/${session.id}`)}
            />
          ))
        )}
      </div>

      {sessions.length > 0 ? (
        <>
          <Separator />
          <div className="text-muted-foreground px-4 py-2 text-center text-[11px]">
            {sessions.length} session{sessions.length === 1 ? "" : "s"}
          </div>
        </>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------

function EmptyState() {
  const router = useRouter();
  const createSession = useCreateThinkingSession();

  const handleStart = async () => {
    try {
      const session = await createSession.mutateAsync({});
      router.push(`/think/${session.id}`);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to create session.",
      );
    }
  };

  return (
    <div className="flex h-full flex-col items-center justify-center text-center">
      <Brain className="text-muted-foreground/30 mb-4 h-12 w-12" />
      <h2 className="font-serif text-xl">Start Thinking</h2>
      <p className="text-muted-foreground mt-1 max-w-sm text-sm">
        Select a session from the list, or create a new one to begin.
      </p>
      <Button
        variant="outline"
        className="mt-4"
        onClick={handleStart}
        disabled={createSession.isPending}
      >
        {createSession.isPending ? (
          <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
        ) : (
          <Plus className="mr-1.5 h-3.5 w-3.5" />
        )}
        New Session
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Client
// ---------------------------------------------------------------------------

export function ThinkClient() {
  return (
    <div className="flex h-[calc(100vh-4rem)] gap-0">
      {/* Left panel: session list */}
      <div className="w-80 shrink-0 overflow-hidden border-r">
        <SessionThreadList />
      </div>

      {/* Right panel: empty state (session editor is on /think/[sessionId]) */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <EmptyState />
      </div>
    </div>
  );
}
