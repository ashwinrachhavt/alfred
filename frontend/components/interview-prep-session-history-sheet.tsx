"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { Clock } from "lucide-react";

import {
  loadPracticeSessionIndex,
  type PracticeSessionSummary,
} from "@/features/interview-prep/practice-session-store";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

function formatRelativeTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";

  const now = Date.now();
  const deltaMs = now - date.getTime();
  const deltaMinutes = Math.floor(deltaMs / 60_000);
  if (deltaMinutes < 1) return "just now";
  if (deltaMinutes < 60) return `${deltaMinutes}m ago`;
  const deltaHours = Math.floor(deltaMinutes / 60);
  if (deltaHours < 24) return `${deltaHours}h ago`;
  const deltaDays = Math.floor(deltaHours / 24);
  return `${deltaDays}d ago`;
}

type InterviewPrepSessionHistorySheetProps = {
  trigger?: React.ReactElement;
};

export function InterviewPrepSessionHistorySheet({ trigger }: InterviewPrepSessionHistorySheetProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const visibleSessions = useMemo<PracticeSessionSummary[]>(
    () => (open ? loadPracticeSessionIndex().slice(0, 20) : []),
    [open],
  );

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        {trigger ?? (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Open recent interview practice sessions"
          >
            <Clock className="h-4 w-4" />
          </Button>
        )}
      </SheetTrigger>

      <SheetContent side="right" className="w-[420px] sm:max-w-[420px]">
        <SheetHeader>
          <SheetTitle>Recent practice sessions</SheetTitle>
        </SheetHeader>

        <div className="flex-1 overflow-auto">
          {visibleSessions.length ? (
            <div className="space-y-3">
              {visibleSessions.map((session) => (
                <div key={session.id} className="bg-background rounded-lg border p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-sm font-medium">{session.company}</p>
                        <span className="text-muted-foreground text-xs">
                          {formatRelativeTimestamp(session.updatedAt)}
                        </span>
                      </div>
                      <p className="text-muted-foreground mt-1 text-xs">
                        {session.role} • {session.id}
                      </p>
                      {session.lastInterviewerPrompt ? (
                        <p className="text-muted-foreground mt-2 line-clamp-3 text-xs">
                          {session.lastInterviewerPrompt}
                        </p>
                      ) : null}
                    </div>

                    <div className="flex shrink-0 items-center gap-1">
                      <SheetClose asChild>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() =>
                            router.push(
                              `/interview-prep?sessionId=${encodeURIComponent(session.id)}`,
                            )
                          }
                        >
                          Open
                        </Button>
                      </SheetClose>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No sessions yet"
              description="Start a practice session to build your local timeline."
              action={
                <SheetClose asChild>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => router.push("/interview-prep")}
                  >
                    Open Interview Prep
                  </Button>
                </SheetClose>
              }
            />
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
