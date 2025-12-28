"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { createSystemDesignSession, getSystemDesignTemplates } from "@/lib/api/system-design";
import type { SystemDesignSession, TemplateDefinition } from "@/lib/api/types/system-design";

import { ApiError } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type RecentSystemDesignSession = {
  id: string;
  shareId: string;
  title: string | null;
  problemStatement: string;
  createdAt: string;
};

const RECENTS_KEY = "alfred:system-design:recents:v1";

function safeParseRecents(raw: string | null): RecentSystemDesignSession[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as RecentSystemDesignSession[]) : [];
  } catch {
    return [];
  }
}

function formatErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

function toRecentSession(session: SystemDesignSession): RecentSystemDesignSession {
  return {
    id: session.id,
    shareId: session.share_id,
    title: session.title ?? null,
    problemStatement: session.problem_statement,
    createdAt: session.created_at,
  };
}

export function SystemDesignStartClient() {
  const router = useRouter();

  const [title, setTitle] = useState("");
  const [problemStatement, setProblemStatement] = useState("");
  const [templateId, setTemplateId] = useState<string | null>(null);

  const [templates, setTemplates] = useState<TemplateDefinition[]>([]);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [recents, setRecents] = useState<RecentSystemDesignSession[]>([]);

  useEffect(() => {
    setRecents(safeParseRecents(window.localStorage.getItem(RECENTS_KEY)));
  }, []);

  useEffect(() => {
    async function loadTemplates() {
      setIsLoadingTemplates(true);
      setError(null);
      try {
        const next = await getSystemDesignTemplates();
        setTemplates(next);
      } catch (err) {
        setError(formatErrorMessage(err));
      } finally {
        setIsLoadingTemplates(false);
      }
    }

    void loadTemplates();
  }, []);

  const canCreate = useMemo(
    () => problemStatement.trim().length > 0 && !isCreating,
    [problemStatement, isCreating],
  );

  async function onCreateSession() {
    setError(null);
    setIsCreating(true);
    try {
      const session = await createSystemDesignSession({
        title: title.trim() || null,
        problem_statement: problemStatement.trim(),
        template_id: templateId,
      });

      const next = [toRecentSession(session), ...recents]
        .filter((item, idx, arr) => arr.findIndex((x) => x.id === item.id) === idx)
        .slice(0, 10);
      setRecents(next);
      window.localStorage.setItem(RECENTS_KEY, JSON.stringify(next));

      router.push(`/system-design/sessions/${session.id}`);
    } catch (err) {
      setError(formatErrorMessage(err));
      setIsCreating(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <div className="space-y-6">
        <header className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">System Design</h1>
          <p className="text-muted-foreground">
            Start a system design interview session with a whiteboard, AI critique, and knowledge
            capture.
          </p>
        </header>

        <Card>
          <CardHeader>
            <CardTitle>New Session</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="sdTitle">Title (optional)</Label>
              <Input
                id="sdTitle"
                placeholder="e.g. Design Twitter"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="sdProblem">Problem statement</Label>
              <Textarea
                id="sdProblem"
                placeholder="Describe the system you want to design (scale, constraints, requirements)."
                value={problemStatement}
                onChange={(e) => setProblemStatement(e.target.value)}
                rows={7}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="sdTemplate">Template</Label>
              <div className="relative">
                <select
                  id="sdTemplate"
                  className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                  value={templateId ?? ""}
                  onChange={(e) => setTemplateId(e.target.value || null)}
                  disabled={isLoadingTemplates}
                >
                  <option value="">No template</option>
                  {templates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>
              {isLoadingTemplates ? (
                <p className="text-xs text-muted-foreground">Loading templates…</p>
              ) : null}
            </div>

            {error ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                {error}
              </div>
            ) : null}
          </CardContent>
          <CardFooter className="flex justify-end">
            <Button onClick={onCreateSession} disabled={!canCreate}>
              {isCreating ? "Creating..." : "Create session"}
            </Button>
          </CardFooter>
        </Card>
      </div>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Recent Sessions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {recents.length ? (
              <ul className="space-y-3">
                {recents.map((s) => (
                  <li key={s.id} className="rounded-lg border p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 space-y-1">
                        <p className="truncate font-medium">{s.title ?? "Untitled session"}</p>
                        <p className="max-h-10 overflow-hidden text-xs text-muted-foreground">
                          {s.problemStatement}
                        </p>
                        <div className="flex flex-wrap gap-2 pt-1">
                          <Badge variant="secondary">id: {s.id}</Badge>
                          <Badge variant="outline">share: {s.shareId}</Badge>
                        </div>
                      </div>
                      <Button asChild variant="outline" size="sm">
                        <Link href={`/system-design/sessions/${s.id}`}>Open</Link>
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                No recent sessions yet. Create one to get started.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
