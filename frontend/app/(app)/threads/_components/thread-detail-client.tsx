"use client";

import Link from "next/link";

import { type ReactNode, useMemo, useState } from "react";

import { ArrowLeft, Copy, RefreshCw, Send } from "lucide-react";
import { toast } from "sonner";

import { copyTextToClipboard } from "@/lib/clipboard";
import { ApiError } from "@/lib/api/client";
import type { ThreadMessage, ThreadMessageRole } from "@/lib/api/types/threads";
import type {
  UnifiedInterviewRequest,
  UnifiedInterviewResponse,
} from "@/lib/api/types/interviews-unified";
import { useAppendThreadMessage } from "@/features/threads/mutations";
import { useThreadMessages } from "@/features/threads/queries";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

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

function formatErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

function roleVariant(role: ThreadMessageRole): "default" | "secondary" | "outline" {
  const normalized = role.toLowerCase();
  if (normalized === "assistant") return "secondary";
  if (normalized === "system") return "outline";
  return "default";
}

function messageHeading(role: ThreadMessageRole): string {
  const normalized = role.toLowerCase();
  if (normalized === "assistant") return "Assistant";
  if (normalized === "system") return "System";
  if (normalized === "user") return "You";
  return role;
}

function sortMessages(messages: ThreadMessage[]): ThreadMessage[] {
  return [...messages].sort((a, b) => {
    const aTs = a.created_at ? Date.parse(a.created_at) : NaN;
    const bTs = b.created_at ? Date.parse(b.created_at) : NaN;
    if (!Number.isNaN(aTs) && !Number.isNaN(bTs)) return aTs - bTs;
    return a.id.localeCompare(b.id);
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function coerceString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function isUnifiedInterviewOperation(
  value: unknown,
): value is UnifiedInterviewResponse["operation"] {
  return value === "collect_questions" || value === "deep_research" || value === "practice_session";
}

function isUnifiedInterviewResponse(value: unknown): value is UnifiedInterviewResponse {
  if (!isRecord(value)) return false;
  if (!isUnifiedInterviewOperation(value.operation)) return false;
  return isRecord(value.metadata);
}

function isUnifiedInterviewRequest(value: unknown): value is UnifiedInterviewRequest {
  if (!isRecord(value)) return false;
  if (!isUnifiedInterviewOperation(value.operation)) return false;
  return typeof value.company === "string";
}

function formatOperationLabel(operation: UnifiedInterviewResponse["operation"]): string {
  if (operation === "collect_questions") return "Collect questions";
  if (operation === "deep_research") return "Deep research";
  return "Practice session";
}

function renderStructuredMessage(message: ThreadMessage): ReactNode | null {
  const data = message.data;
  const dataType = coerceString(data?.type);
  const payload = isRecord(data?.payload) ? data.payload : null;

  if (dataType === "unified_interview_request" && payload && isUnifiedInterviewRequest(payload)) {
    return (
      <div className="space-y-2 text-sm">
        <p className="text-muted-foreground">
          Interview prep request · {formatOperationLabel(payload.operation)}
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          <div>
            <p className="text-muted-foreground text-xs">Company</p>
            <p className="font-medium">{payload.company}</p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs">Role</p>
            <p className="font-medium">{payload.role ?? "Software Engineer"}</p>
          </div>
        </div>
        <details>
          <summary className="text-muted-foreground cursor-pointer text-xs select-none">
            Raw payload
          </summary>
          <pre className="bg-muted/30 mt-2 max-h-[320px] overflow-auto rounded-md border p-3 text-xs leading-relaxed">
            {JSON.stringify(payload, null, 2)}
          </pre>
        </details>
      </div>
    );
  }

  if (dataType === "unified_interview_response" && payload && isUnifiedInterviewResponse(payload)) {
    return (
      <div className="space-y-3 text-sm">
        <p className="text-muted-foreground">
          Interview prep result · {formatOperationLabel(payload.operation)}
        </p>

        {payload.operation === "collect_questions" ? (
          <div className="space-y-2">
            <p className="font-medium">Questions</p>
            {(payload.questions ?? []).length ? (
              <div className="space-y-2">
                {(payload.questions ?? []).map((q, idx) => (
                  <div key={`${idx}:${q.question}`} className="rounded-md border p-3">
                    <p className="text-muted-foreground text-xs">Q{idx + 1}</p>
                    <p className="whitespace-pre-wrap">{q.question}</p>
                    {q.categories?.length ? (
                      <p className="text-muted-foreground mt-1 text-xs">
                        Categories: {q.categories.join(", ")}
                      </p>
                    ) : null}
                    {q.sources?.length ? (
                      <div className="mt-2 space-y-1">
                        <p className="text-muted-foreground text-xs">Sources</p>
                        <div className="flex flex-col gap-1 text-xs">
                          {q.sources.map((url) => (
                            <a
                              key={url}
                              href={url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-primary truncate underline underline-offset-4"
                            >
                              {url}
                            </a>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">No questions returned.</p>
            )}
          </div>
        ) : null}

        {payload.operation === "deep_research" ? (
          <div className="space-y-2">
            <p className="font-medium">Research report</p>
            <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap">
              {payload.research_report || "—"}
            </div>
          </div>
        ) : null}

        {payload.operation === "practice_session" ? (
          <div className="space-y-2">
            <p className="font-medium">Interviewer response</p>
            <p className="text-muted-foreground whitespace-pre-wrap">
              {payload.interviewer_response || "—"}
            </p>
          </div>
        ) : null}

        <details>
          <summary className="text-muted-foreground cursor-pointer text-xs select-none">
            Raw payload
          </summary>
          <pre className="bg-muted/30 mt-2 max-h-[420px] overflow-auto rounded-md border p-3 text-xs leading-relaxed">
            {JSON.stringify(payload, null, 2)}
          </pre>
        </details>
      </div>
    );
  }

  if (isRecord(data) && Object.keys(data).length) {
    return (
      <details>
        <summary className="text-muted-foreground cursor-pointer text-xs select-none">
          Structured data
        </summary>
        <pre className="bg-muted/30 mt-2 max-h-[420px] overflow-auto rounded-md border p-3 text-xs leading-relaxed">
          {JSON.stringify(data, null, 2)}
        </pre>
      </details>
    );
  }

  return null;
}

export function ThreadDetailClient({ threadId }: { threadId: string }) {
  const safeThreadId = threadId?.trim() ?? "";
  const messagesQuery = useThreadMessages(safeThreadId);
  const appendMutation = useAppendThreadMessage(safeThreadId);

  const [role, setRole] = useState<ThreadMessageRole>("user");
  const [content, setContent] = useState("");

  const errorMessage = messagesQuery.isError ? formatErrorMessage(messagesQuery.error) : null;

  const messages = useMemo(() => sortMessages(messagesQuery.data ?? []), [messagesQuery.data]);

  async function copyThreadId() {
    try {
      await copyTextToClipboard(safeThreadId);
      toast.success("Copied thread id");
    } catch (err) {
      toast.error("Could not copy", { description: formatErrorMessage(err) });
    }
  }

  async function onSend() {
    const next = content.trim();
    if (!next) return;

    try {
      await appendMutation.mutateAsync({ role, content: next });
      setContent("");
      toast.success("Message appended");
    } catch (err) {
      toast.error("Could not append", { description: formatErrorMessage(err) });
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Button asChild variant="ghost" size="sm">
            <Link href="/threads">
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Back
            </Link>
          </Button>
          <Separator orientation="vertical" className="h-5" />
          <h1 className="text-2xl font-semibold tracking-tight">Thread</h1>
          <Badge variant="outline">{safeThreadId ? safeThreadId.slice(0, 8) : "—"}</Badge>
        </div>
        <p className="text-muted-foreground text-sm">
          Thread id: {safeThreadId || "Missing thread id"}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={() => void copyThreadId()}>
            <Copy className="h-4 w-4" aria-hidden="true" />
            Copy id
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => void messagesQuery.refetch()}
            disabled={messagesQuery.isFetching}
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </Button>
        </div>
      </header>

      {errorMessage ? (
        <Alert variant="destructive">
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>
      ) : !safeThreadId ? (
        <Alert variant="destructive">
          <AlertDescription>
            This page is missing a thread id. Go back to the threads list and open a thread again.
          </AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Append message</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="messageRole">Role</Label>
              <Input
                id="messageRole"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="user | assistant | system | note"
              />
            </div>
            <div className="space-y-2">
              <Label>Thread</Label>
              <Input value={safeThreadId} readOnly />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="messageContent">Content</Label>
            <Textarea
              id="messageContent"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Write a message…"
              rows={5}
            />
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              onClick={() => void onSend()}
              disabled={appendMutation.isPending || !content.trim() || !safeThreadId}
            >
              <Send className="h-4 w-4" aria-hidden="true" />
              Send
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => void messagesQuery.refetch()}
              disabled={messagesQuery.isFetching || !safeThreadId}
            >
              Refresh messages
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <CardTitle>Messages</CardTitle>
            <p className="text-muted-foreground text-sm">
              {messagesQuery.isLoading ? "Loading…" : `${messages.length} total`}
            </p>
          </div>
        </CardHeader>
        <CardContent>
          {messagesQuery.isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : messages.length ? (
            <div className="space-y-3">
              {messages.map((message) => (
                <div key={message.id} className="rounded-lg border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge variant={roleVariant(message.role)}>
                        {messageHeading(message.role)}
                      </Badge>
                      <span className="text-muted-foreground text-xs">
                        {formatMaybeDate(message.created_at)}
                      </span>
                    </div>
                    <Badge variant="outline" className="text-xs">
                      {message.id.slice(0, 8)}
                    </Badge>
                  </div>
                  <div className="mt-3 text-sm leading-relaxed whitespace-pre-wrap">
                    {message.content?.trim()
                      ? message.content
                      : (renderStructuredMessage(message) ?? "—")}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No messages yet" description="Append a message to start." />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
