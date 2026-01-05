"use client";

import { useMemo, useState } from "react";

import { toast } from "sonner";

import { useTaskStatus } from "@/features/tasks/queries";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function TasksClient({ initialTaskId }: { initialTaskId?: string }) {
  const [taskId, setTaskId] = useState<string>(initialTaskId ?? "");
  const trimmedTaskId = useMemo(() => taskId.trim(), [taskId]);
  const { data, error, isFetching } = useTaskStatus(trimmedTaskId ? trimmedTaskId : null);

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
        ) : (
          <p className="text-muted-foreground text-sm">
            Enter a task id to poll status from the API.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
