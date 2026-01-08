"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { toast } from "sonner";

import { useTaskStatus } from "@/features/tasks/queries";

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

export function TasksClient({ initialTaskId }: { initialTaskId?: string }) {
  const [taskId, setTaskId] = useState<string>(initialTaskId ?? "");
  const trimmedTaskId = useMemo(() => taskId.trim(), [taskId]);
  const { data, error, isFetching } = useTaskStatus(trimmedTaskId ? trimmedTaskId : null);

  const companyReportId = useMemo(() => extractCompanyResearchReportId(data?.result), [data?.result]);
  const companyReportHref = companyReportId ? `/company?reportId=${encodeURIComponent(companyReportId)}` : null;
  const executiveSummary = useMemo(
    () => extractCompanyResearchExecutiveSummary(data?.result),
    [data?.result],
  );

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
                          await navigator.clipboard.writeText(
                            JSON.stringify(data.result, null, 2),
                          );
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

                {executiveSummary ? (
                  <p className="text-muted-foreground whitespace-pre-wrap">{executiveSummary}</p>
                ) : null}

                <Separator />

                <pre className="bg-muted/30 max-h-[420px] overflow-auto rounded-md border p-3 text-xs leading-relaxed">
                  {JSON.stringify(data.result, null, 2)}
                </pre>
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
