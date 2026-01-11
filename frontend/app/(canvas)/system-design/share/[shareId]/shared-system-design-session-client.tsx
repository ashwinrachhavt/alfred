"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { getSharedSystemDesignSession } from "@/lib/api/system-design";
import type { SystemDesignSession } from "@/lib/api/types/system-design";

import { ApiError } from "@/lib/api/client";
import { ExcalidrawCanvas } from "@/components/system-design/excalidraw-canvas";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

function formatErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

export function SharedSystemDesignSessionClient({ shareId }: { shareId: string }) {
  const searchParams = useSearchParams();
  const isEmbed = searchParams.get("embed") === "1";

  const [session, setSession] = useState<SystemDesignSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [needsPassword, setNeedsPassword] = useState(false);

  async function load(pass?: string) {
    setIsLoading(true);
    setError(null);
    try {
      const next = await getSharedSystemDesignSession(
        shareId,
        pass ? { password: pass } : undefined,
      );
      setSession(next);
      setNeedsPassword(false);
    } catch (err) {
      setSession(null);
      if (err instanceof ApiError && err.status === 401) {
        setNeedsPassword(true);
      }
      setError(formatErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [shareId]);

  const title = useMemo(() => session?.title ?? "Shared System Design Session", [session]);

  if (isLoading) {
    return (
      <div className="text-muted-foreground flex h-full w-full items-center justify-center text-sm">
        Loading shared session…
      </div>
    );
  }

  if (!session) {
    if (needsPassword) {
      return (
        <div className="mx-auto w-full max-w-md space-y-4 px-4 py-10">
          <h1 className="text-2xl font-semibold">{title}</h1>
          <p className="text-muted-foreground text-sm">{error ?? "Password required."}</p>

          <div className="bg-background space-y-3 rounded-xl border p-4">
            <div className="space-y-2">
              <Label htmlFor="sdSharePassword">Password</Label>
              <Input
                id="sdSharePassword"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password…"
              />
            </div>
            <div className="flex items-center justify-between gap-2">
              <Button onClick={() => void load(password)} disabled={!password.trim() || isLoading}>
                {isLoading ? "Unlocking…" : "Unlock"}
              </Button>
              {!isEmbed ? (
                <Button asChild variant="outline">
                  <Link href="/system-design">Back</Link>
                </Button>
              ) : null}
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="mx-auto w-full max-w-3xl space-y-4 px-4 py-10">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="text-muted-foreground text-sm">{error ?? "Session not found."}</p>
        <Button asChild variant="outline">
          <Link href="/system-design">Back</Link>
        </Button>
      </div>
    );
  }

  if (isEmbed) {
    return (
      <div className="h-full w-full">
        <ExcalidrawCanvas initialDiagram={session.diagram} readOnly framed={false} viewportScale={1} />
      </div>
    );
  }

  return (
    <div className="grid h-full grid-cols-1 gap-3 p-2 lg:grid-cols-[1fr_360px]">
      <div className="flex min-h-0 flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
            <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
              <Badge variant="secondary">share: {session.share_id}</Badge>
              <Badge variant="outline">id: {session.id}</Badge>
            </div>
          </div>
          <Button asChild variant="ghost">
            <Link href="/system-design">Exit</Link>
          </Button>
        </div>

        <details className="bg-background rounded-xl border">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium select-none">
            Problem statement
            <span className="text-muted-foreground ml-2 text-xs font-normal">
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
          <p className="text-muted-foreground text-xs">
            This is a read-only snapshot. To continue editing, open the original session.
          </p>
        </Card>
      </div>
    </div>
  );
}
