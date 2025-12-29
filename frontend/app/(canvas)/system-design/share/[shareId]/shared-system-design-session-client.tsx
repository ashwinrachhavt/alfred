"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { getSharedSystemDesignSession } from "@/lib/api/system-design";
import type { SystemDesignSession } from "@/lib/api/types/system-design";

import { ApiError } from "@/lib/api/client";
import { ExcalidrawCanvas } from "@/components/system-design/excalidraw-canvas";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

function formatErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

export function SharedSystemDesignSessionClient({ shareId }: { shareId: string }) {
  const [session, setSession] = useState<SystemDesignSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const next = await getSharedSystemDesignSession(shareId);
        setSession(next);
      } catch (err) {
        setError(formatErrorMessage(err));
      } finally {
        setIsLoading(false);
      }
    }
    void load();
  }, [shareId]);

  const title = useMemo(
    () => session?.title ?? "Shared System Design Session",
    [session],
  );

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
        Loading shared session…
      </div>
    );
  }

  if (!session) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-10 space-y-4">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="text-sm text-muted-foreground">{error ?? "Session not found."}</p>
        <Button asChild variant="outline">
          <Link href="/system-design">Back</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="grid h-full grid-cols-1 gap-3 p-2 lg:grid-cols-[1fr_360px]">
      <div className="flex min-h-0 flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="secondary">share: {session.share_id}</Badge>
              <Badge variant="outline">id: {session.id}</Badge>
            </div>
          </div>
          <Button asChild variant="ghost">
            <Link href="/system-design">Exit</Link>
          </Button>
        </div>

        <details className="rounded-xl border bg-background">
          <summary className="cursor-pointer select-none px-4 py-3 text-sm font-medium">
            Problem statement
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              (click to expand)
            </span>
          </summary>
          <div className="px-4 pb-4">
            <Textarea value={session.problem_statement} readOnly rows={6} className="resize-none" />
          </div>
        </details>

        <div className="min-h-0 flex-1">
          <ExcalidrawCanvas initialDiagram={session.diagram} readOnly viewportScale={0.5} />
        </div>
      </div>

      <div className="min-h-0">
        <Card className="h-full p-4">
          <p className="text-sm font-medium">Shared view</p>
          <p className="text-xs text-muted-foreground">
            This is a read-only snapshot. To continue editing, open the original session.
          </p>
        </Card>
      </div>
    </div>
  );
}
