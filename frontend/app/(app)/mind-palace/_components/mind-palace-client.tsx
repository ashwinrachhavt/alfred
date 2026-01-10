"use client";

import { useMemo, useState } from "react";

import { Brain, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { queryMindPalaceAgent } from "@/lib/api/mind-palace";
import type {
  AgentQueryRequest,
  MindPalaceQueryResponse,
} from "@/lib/api/types/mind-palace";

import { useTaskTracker } from "@/features/tasks/task-tracker-provider";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { JsonViewer } from "@/components/ui/json-viewer";

function safeParseJsonObject(raw: string): Record<string, unknown> | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
    return null;
  } catch {
    return null;
  }
}

function extractTaskId(payload: MindPalaceQueryResponse | null): string | null {
  if (!payload || typeof payload !== "object") return null;
  const maybeTask = (payload as { task_id?: unknown }).task_id;
  return typeof maybeTask === "string" && maybeTask.trim() ? maybeTask : null;
}

export function MindPalaceClient() {
  const { trackTask } = useTaskTracker();

  const [question, setQuestion] = useState("");
  const [historyJson, setHistoryJson] = useState("[]");
  const [contextJson, setContextJson] = useState("{}");
  const [background, setBackground] = useState(false);

  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<MindPalaceQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const context = useMemo(() => safeParseJsonObject(contextJson), [contextJson]);
  const parsedHistory = useMemo(() => {
    const trimmed = historyJson.trim();
    if (!trimmed) return null;
    try {
      const parsed = JSON.parse(trimmed) as unknown;
      return Array.isArray(parsed) ? parsed : null;
    } catch {
      return null;
    }
  }, [historyJson]);

  async function run() {
    const q = question.trim();
    if (!q) return;
    setIsRunning(true);
    setError(null);
    setResult(null);

    const payload: AgentQueryRequest = { question: q };
    if (Array.isArray(parsedHistory)) payload.history = parsedHistory as AgentQueryRequest["history"];
    if (context) payload.context = context;

    try {
      const res = await queryMindPalaceAgent(payload, { background });
      setResult(res);
      const taskId = extractTaskId(res);
      if (taskId) {
        trackTask({
          id: taskId,
          source: "mind_palace",
          label: "Mind Palace agent query",
          href: "/mind-palace",
        });
        toast.message("Queued in background.", { description: "Track progress in Tasks." });
      } else {
        toast.success("Answer ready.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setIsRunning(false);
    }
  }

  const answer = useMemo(() => {
    if (!result || typeof result !== "object") return null;
    const value = (result as { answer?: unknown }).answer;
    return typeof value === "string" ? value : null;
  }, [result]);

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <Brain className="text-muted-foreground h-5 w-5" aria-hidden="true" />
          <h1 className="text-3xl font-semibold tracking-tight">Mind Palace</h1>
        </div>
        <p className="text-muted-foreground">
          Query the agent with optional history + structured context.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Query</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="mpQuestion">Question</Label>
            <Textarea
              id="mpQuestion"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask anything…"
              rows={4}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="mpHistory">History (JSON array)</Label>
              <Textarea
                id="mpHistory"
                value={historyJson}
                onChange={(e) => setHistoryJson(e.target.value)}
                rows={6}
              />
              <p className="text-muted-foreground text-xs">
                Example: <code>{`[{"role":"user","content":"…"}]`}</code>
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="mpContext">Context (JSON object)</Label>
              <Textarea
                id="mpContext"
                value={contextJson}
                onChange={(e) => setContextJson(e.target.value)}
                rows={6}
              />
              <p className="text-muted-foreground text-xs">
                Use this to pass structured state without polluting the question.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-1">
              <p className="text-sm font-medium">Background</p>
              <p className="text-muted-foreground text-xs">Enqueue as a task instead of blocking.</p>
            </div>
            <Switch checked={background} onCheckedChange={setBackground} />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" onClick={() => void run()} disabled={isRunning || !question.trim()}>
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              {isRunning ? "Running…" : "Run"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setResult(null);
                setError(null);
              }}
              disabled={isRunning}
            >
              Clear
            </Button>
          </div>

          {error ? <p className="text-destructive text-sm">{error}</p> : null}
        </CardContent>
      </Card>

      {answer ? (
        <Card>
          <CardHeader>
            <CardTitle>Answer</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{answer}</p>
          </CardContent>
        </Card>
      ) : null}

      {result ? <JsonViewer value={result} title="Raw response" collapsed /> : null}
    </div>
  );
}
