"use client"

import { useState } from "react"

import { toast } from "sonner"

import { useTaskStatus } from "@/features/tasks/queries"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

export default function TasksPage() {
  const [taskId, setTaskId] = useState<string>("")
  const { data, error, isFetching } = useTaskStatus(taskId.trim() ? taskId.trim() : null)

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10">
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
                setTaskId("")
                toast.message("Cleared task id.")
              }}
            >
              Clear
            </Button>
          </div>

          {error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm">
              <p className="font-medium">Could not load task status</p>
              <p className="text-muted-foreground">
                {error instanceof Error ? error.message : "Unknown error"}
              </p>
            </div>
          ) : null}

          {data ? (
            <div className="rounded-lg border bg-background p-4 text-sm">
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-medium">{data.task_id}</span>
                <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                  {data.status}
                </span>
                <span className="text-xs text-muted-foreground">
                  {isFetching ? "Updating…" : "Idle"}
                </span>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <div>
                  <p className="text-xs text-muted-foreground">Ready</p>
                  <p className="font-medium">{String(data.ready)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Successful</p>
                  <p className="font-medium">{String(data.successful)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Failed</p>
                  <p className="font-medium">{String(data.failed)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Error</p>
                  <p className="truncate font-medium">{data.error ?? "—"}</p>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Enter a task id to poll status from the API.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
