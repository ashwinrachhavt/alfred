"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { toast } from "sonner";

import { useTaskStatus } from "@/features/tasks/queries";
import { appendThreadMessage, createThread } from "@/lib/api/threads";
import type {
  UnifiedInterviewOperation,
  UnifiedInterviewResponse,
  UnifiedQuestion,
} from "@/lib/api/types/interviews-unified";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function coerceString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function extractCompanyResearchReportId(result: unknown): string | null {
  if (!isRecord(result)) return null;
  const id = coerceString(result.id);
  const report = isRecord(result.report) ? result.report : null;
  const hasReport = Boolean(report);
  if (!id || !hasReport) return null;
  return id.trim() || null;
}

function extractCompanyResearchExecutiveSummary(result: unknown): string | null {
  if (!isRecord(result)) return null;
  const report = isRecord(result.report) ? result.report : null;
  if (!report) return null;
  const summary = coerceString(report.executive_summary);
  return summary?.trim() || null;
}

function extractThreadIdFromTaskResult(result: unknown): string | null {
  if (!isRecord(result)) return null;
  const metadata = isRecord(result.metadata) ? result.metadata : null;
  const threadId = metadata ? coerceString(metadata.thread_id) : null;
  return threadId?.trim() || null;
}

function isUnifiedInterviewOperation(value: unknown): value is UnifiedInterviewOperation {
  return value === "collect_questions" || value === "deep_research" || value === "practice_session";
}

function isUnifiedInterviewResponse(result: unknown): result is UnifiedInterviewResponse {
  if (!isRecord(result)) return false;
  if (!isUnifiedInterviewOperation(result.operation)) return false;
  return isRecord(result.metadata);
}

function formatUnifiedInterviewMarkdown(result: UnifiedInterviewResponse): string {
  const lines: string[] = [];

  lines.push(`# Interview Prep — ${formatOperationLabel(result.operation)}`);
  if (typeof result.sources_scraped === "number")
    lines.push(`Sources scraped: ${result.sources_scraped}`);
  lines.push("");

  if (result.operation === "collect_questions") {
    const questions = result.questions ?? [];
    lines.push("## Questions");
    if (!questions.length) {
      lines.push("_No questions returned._");
      return `${lines.join("\n").trim()}\n`;
    }

    questions.forEach((question, idx) => {
      lines.push(`${idx + 1}. ${question.question}`);
      if (question.categories?.length)
        lines.push(`   - Categories: ${question.categories.join(", ")}`);
      if (question.sources?.length) lines.push(`   - Sources: ${question.sources.join(", ")}`);
      if (question.solution?.approach) lines.push(`   - Approach: ${question.solution.approach}`);
      lines.push("");
    });

    return `${lines.join("\n").trim()}\n`;
  }

  if (result.operation === "deep_research") {
    if (result.key_insights?.length) {
      lines.push("## Key insights");
      result.key_insights.forEach((insight) => lines.push(`- ${insight}`));
      lines.push("");
    }

    lines.push("## Research report");
    lines.push(result.research_report?.trim() || "_No report returned._");
    return `${lines.join("\n").trim()}\n`;
  }

  lines.push("## Interviewer response");
  lines.push(result.interviewer_response?.trim() || "_No response returned._");
  lines.push("");
  lines.push("## Feedback");
  lines.push(JSON.stringify(result.feedback ?? {}, null, 2));
  return `${lines.join("\n").trim()}\n`;
}

function formatOperationLabel(operation: UnifiedInterviewOperation): string {
  if (operation === "collect_questions") return "Collect questions";
  if (operation === "deep_research") return "Deep research";
  return "Practice session";
}

function QuestionCard({ question, index }: { question: UnifiedQuestion; index: number }) {
  const sources = question.sources ?? [];
  const categories = question.categories ?? [];

  return (
    <div className="space-y-2 rounded-lg border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted-foreground text-xs">Q{index + 1}</span>
        {categories.map((category) => (
          <span
            key={category}
            className="text-muted-foreground rounded-full border px-2 py-0.5 text-xs"
          >
            {category}
          </span>
        ))}
        {typeof question.occurrences === "number" && question.occurrences > 1 ? (
          <span className="text-muted-foreground text-xs">×{question.occurrences}</span>
        ) : null}
      </div>

      <p className="text-sm leading-relaxed whitespace-pre-wrap">{question.question}</p>

      {sources.length ? (
        <div className="flex flex-col gap-1">
          <p className="text-muted-foreground text-xs">Sources</p>
          <div className="flex flex-col gap-1 text-xs">
            {sources.map((url) => (
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

      {question.validation ? (
        <details className="text-xs">
          <summary className="text-muted-foreground cursor-pointer select-none">Validation</summary>
          <div className="mt-2 space-y-1 whitespace-pre-wrap">
            <p>Valid: {String(question.validation.is_valid)}</p>
            <p>Confidence: {question.validation.confidence}</p>
            <p className="text-muted-foreground">{question.validation.reasoning}</p>
          </div>
        </details>
      ) : null}

      {question.solution?.approach ? (
        <details className="text-xs">
          <summary className="text-muted-foreground cursor-pointer select-none">Solution</summary>
          <div className="mt-2 space-y-2 whitespace-pre-wrap">
            <p>{question.solution.approach}</p>
            {question.solution.key_insights?.length ? (
              <ul className="list-disc space-y-1 pl-5">
                {question.solution.key_insights.map((insight) => (
                  <li key={insight}>{insight}</li>
                ))}
              </ul>
            ) : null}
            {(question.solution.time_complexity || question.solution.space_complexity) && (
              <p className="text-muted-foreground">
                {question.solution.time_complexity
                  ? `Time: ${question.solution.time_complexity}`
                  : ""}
                {question.solution.time_complexity && question.solution.space_complexity
                  ? " · "
                  : ""}
                {question.solution.space_complexity
                  ? `Space: ${question.solution.space_complexity}`
                  : ""}
              </p>
            )}
          </div>
        </details>
      ) : null}
    </div>
  );
}

export function TasksClient({ initialTaskId }: { initialTaskId?: string }) {
  const router = useRouter();
  const [taskId, setTaskId] = useState<string>(initialTaskId ?? "");
  const trimmedTaskId = useMemo(() => taskId.trim(), [taskId]);
  const { data, error, isFetching } = useTaskStatus(trimmedTaskId ? trimmedTaskId : null);
  const [isSavingToThread, setIsSavingToThread] = useState(false);

  const companyReportId = useMemo(
    () => extractCompanyResearchReportId(data?.result),
    [data?.result],
  );
  const companyReportHref = companyReportId
    ? `/company?reportId=${encodeURIComponent(companyReportId)}`
    : null;
  const executiveSummary = useMemo(
    () => extractCompanyResearchExecutiveSummary(data?.result),
    [data?.result],
  );

  const unifiedInterview = useMemo(() => {
    const result = data?.result;
    if (!isUnifiedInterviewResponse(result)) return null;
    return result;
  }, [data?.result]);

  const resultThreadId = useMemo(() => extractThreadIdFromTaskResult(data?.result), [data?.result]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Background Tasks</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Input
            placeholder="Paste task id…"
            value={taskId}
            onChange={(event) => setTaskId(event.target.value)}
          />
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setTaskId("");
              toast.message("Cleared task id.");
            }}
          >
            Clear
          </Button>
        </div>

        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Could not load task status</AlertTitle>
            <AlertDescription>
              {error instanceof Error ? error.message : "Unknown error"}
            </AlertDescription>
          </Alert>
        ) : null}

        {data ? (
          <div className="space-y-4">
            <div className="bg-background rounded-lg border p-4 text-sm">
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-medium">{data.task_id}</span>
                <span className="text-muted-foreground rounded-full border px-2 py-0.5 text-xs">
                  {data.status}
                </span>
                <span className="text-muted-foreground text-xs">
                  {isFetching ? "Updating…" : "Idle"}
                </span>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <div>
                  <p className="text-muted-foreground text-xs">Ready</p>
                  <p className="font-medium">{String(data.ready)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Successful</p>
                  <p className="font-medium">{String(data.successful)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Failed</p>
                  <p className="font-medium">{String(data.failed)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Error</p>
                  <p className="truncate font-medium">{data.error ?? "—"}</p>
                </div>
              </div>
            </div>

            {data.ready && data.result ? (
              <div className="bg-background space-y-3 rounded-lg border p-4 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">Result</p>
                  <div className="flex flex-wrap gap-2">
                    {resultThreadId ? (
                      <Button asChild size="sm" variant="secondary">
                        <Link href={`/threads/${encodeURIComponent(resultThreadId)}`}>
                          Open in Threads
                        </Link>
                      </Button>
                    ) : unifiedInterview ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        disabled={isSavingToThread}
                        onClick={async () => {
                          setIsSavingToThread(true);
                          try {
                            const thread = await createThread({
                              kind: "tasks",
                              title: `Interview prep — ${formatOperationLabel(unifiedInterview.operation)}`,
                              metadata: {
                                source: "tasks",
                                task_id: data.task_id,
                              },
                            });
                            await appendThreadMessage(thread.id, {
                              role: "assistant",
                              content: formatUnifiedInterviewMarkdown(unifiedInterview),
                              data: {
                                type: "task_result",
                                task_id: data.task_id,
                                operation: unifiedInterview.operation,
                              },
                            });
                            toast.success("Saved to Threads.");
                            router.push(`/threads/${thread.id}`);
                          } catch (err) {
                            toast.error(
                              err instanceof Error ? err.message : "Failed to save to Threads.",
                            );
                          } finally {
                            setIsSavingToThread(false);
                          }
                        }}
                      >
                        {isSavingToThread ? "Saving…" : "Save to Threads"}
                      </Button>
                    ) : null}
                    {companyReportHref ? (
                      <Button asChild size="sm" variant="secondary">
                        <Link href={companyReportHref}>Open company report</Link>
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(JSON.stringify(data.result, null, 2));
                          toast.success("Copied task result JSON.");
                        } catch {
                          toast.error("Failed to copy result.");
                        }
                      }}
                    >
                      Copy JSON
                    </Button>
                  </div>
                </div>

                {unifiedInterview ? (
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-muted-foreground rounded-full border px-2 py-0.5 text-xs">
                        {formatOperationLabel(unifiedInterview.operation)}
                      </span>
                      {typeof unifiedInterview.sources_scraped === "number" ? (
                        <span className="text-muted-foreground text-xs">
                          Sources scraped: {unifiedInterview.sources_scraped}
                        </span>
                      ) : null}
                      {isRecord(unifiedInterview.metadata) ? (
                        <span className="text-muted-foreground text-xs">
                          Total questions:{" "}
                          {String(unifiedInterview.metadata.total_questions_collected ?? "—")}
                        </span>
                      ) : null}
                    </div>

                    {unifiedInterview.operation === "collect_questions" ? (
                      <div className="space-y-3">
                        <p className="font-medium">Questions</p>
                        {(unifiedInterview.questions ?? []).length ? (
                          <div className="space-y-3">
                            {(unifiedInterview.questions ?? []).map((q, idx) => (
                              <QuestionCard key={`${idx}:${q.question}`} question={q} index={idx} />
                            ))}
                          </div>
                        ) : (
                          <p className="text-muted-foreground text-sm">No questions returned.</p>
                        )}
                      </div>
                    ) : null}

                    {unifiedInterview.operation === "deep_research" ? (
                      <div className="space-y-3">
                        {unifiedInterview.key_insights?.length ? (
                          <div className="space-y-2">
                            <p className="font-medium">Key insights</p>
                            <ul className="list-disc space-y-1 pl-5 text-sm">
                              {unifiedInterview.key_insights.map((insight) => (
                                <li key={insight}>{insight}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}

                        <div className="space-y-2">
                          <p className="font-medium">Research report</p>
                          <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap">
                            {unifiedInterview.research_report || "—"}
                          </div>
                        </div>
                      </div>
                    ) : null}

                    {unifiedInterview.operation === "practice_session" ? (
                      <div className="space-y-2">
                        <p className="font-medium">Interviewer response</p>
                        <p className="text-muted-foreground text-sm whitespace-pre-wrap">
                          {unifiedInterview.interviewer_response || "—"}
                        </p>
                      </div>
                    ) : null}

                    <Separator />

                    <details>
                      <summary className="text-muted-foreground cursor-pointer text-sm select-none">
                        Raw JSON
                      </summary>
                      <pre className="bg-muted/30 mt-3 max-h-[420px] overflow-auto rounded-md border p-3 text-xs leading-relaxed">
                        {JSON.stringify(data.result, null, 2)}
                      </pre>
                    </details>
                  </div>
                ) : null}

                {executiveSummary ? (
                  <p className="text-muted-foreground whitespace-pre-wrap">{executiveSummary}</p>
                ) : null}

                {!unifiedInterview ? (
                  <>
                    <Separator />
                    <pre className="bg-muted/30 max-h-[420px] overflow-auto rounded-md border p-3 text-xs leading-relaxed">
                      {JSON.stringify(data.result, null, 2)}
                    </pre>
                  </>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">
            Enter a task id to poll status from the API.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
