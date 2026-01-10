"use client";

import { useMemo, useState } from "react";

import { MessageCircle, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { ragAnswer } from "@/lib/api/rag";
import type { RagAnswerMode, RagAnswerResponse } from "@/lib/api/types/rag";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { JsonViewer } from "@/components/ui/json-viewer";

function extractAnswerText(payload: RagAnswerResponse | null): string | null {
  if (!payload) return null;
  const maybeAnswer = payload.answer;
  if (typeof maybeAnswer === "string" && maybeAnswer.trim()) return maybeAnswer;
  const maybeOutput = payload.output;
  if (typeof maybeOutput === "string" && maybeOutput.trim()) return maybeOutput;
  const maybeText = payload.text;
  if (typeof maybeText === "string" && maybeText.trim()) return maybeText;
  return null;
}

const MODES: RagAnswerMode[] = ["minimal", "concise", "formal", "deep"];

export function RagClient() {
  const [q, setQ] = useState("");
  const [k, setK] = useState(4);
  const [includeContext, setIncludeContext] = useState(false);
  const [mode, setMode] = useState<RagAnswerMode>("minimal");

  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<RagAnswerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const answerText = useMemo(() => extractAnswerText(result), [result]);

  const contextSummary = useMemo(() => {
    if (!includeContext || !result) return null;
    const context = result.context;
    if (Array.isArray(context)) return `${context.length} retrieved items`;
    if (context && typeof context === "object") return "Context returned";
    return null;
  }, [includeContext, result]);

  async function run() {
    const query = q.trim();
    if (!query) return;
    setIsLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await ragAnswer({
        q: query,
        k: Math.max(1, Math.min(20, k)),
        include_context: includeContext,
        mode,
      });
      setResult(res);
      toast.success("Answer ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <MessageCircle className="text-muted-foreground h-5 w-5" aria-hidden="true" />
          <h1 className="text-3xl font-semibold tracking-tight">Knowledge Assistant</h1>
        </div>
        <p className="text-muted-foreground">
          Ask questions across your knowledge base. Enable context when you want citations and
          retrieved snippets.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Ask</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="ragQ">Question</Label>
            <Textarea
              id="ragQ"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="e.g. What did I capture about vector databases last week?"
              rows={4}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="ragK">Top-k</Label>
              <Input
                id="ragK"
                inputMode="numeric"
                value={String(k)}
                onChange={(e) => setK(Number(e.target.value))}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="ragMode">Mode</Label>
              <select
                id="ragMode"
                className="bg-background h-10 w-full rounded-md border px-3 text-sm"
                value={mode}
                onChange={(e) => setMode(e.target.value as RagAnswerMode)}
              >
                {MODES.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center justify-between rounded-lg border p-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">Include context</p>
                <p className="text-muted-foreground text-xs">Return retrieved items metadata.</p>
              </div>
              <Switch checked={includeContext} onCheckedChange={setIncludeContext} />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" onClick={() => void run()} disabled={!q.trim() || isLoading}>
              {isLoading ? "Thinking…" : "Answer"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setResult(null);
                setError(null);
              }}
              disabled={isLoading}
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Reset
            </Button>
          </div>

          {error ? <p className="text-destructive text-sm">{error}</p> : null}
        </CardContent>
      </Card>

      {answerText ? (
        <Card>
          <CardHeader>
            <CardTitle>Answer</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{answerText}</p>
            {contextSummary ? (
              <>
                <Separator />
                <p className="text-muted-foreground text-xs">{contextSummary}</p>
              </>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {result ? <JsonViewer value={result} title="Raw response" collapsed /> : null}
    </div>
  );
}

