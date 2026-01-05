"use client"

import { useMemo, useState } from "react"

import { toast } from "sonner"

import type { CompanyResearchPayload, CompanyResearchQueuedResponse } from "@/lib/api/types/company"
import { useStartCompanyResearch } from "@/features/company/mutations"
import { useTaskStatus } from "@/features/tasks/queries"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"

function isQueuedResponse(value: unknown): value is CompanyResearchQueuedResponse {
  return value !== null && typeof value === "object" && "task_id" in value && "status_url" in value
}

function normalizeCompanyResearchResult(value: unknown): CompanyResearchPayload | null {
  if (!value || typeof value !== "object") return null
  if (!("report" in value)) return null
  return value as CompanyResearchPayload
}

function BulletList({ items }: { items: string[] }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">—</p>
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm">
      {items.map((item, idx) => (
        <li key={`${idx}-${item.slice(0, 16)}`}>{item}</li>
      ))}
    </ul>
  )
}

function ResearchReport({ payload }: { payload: CompanyResearchPayload }) {
  const report = payload.report

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Executive Summary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="whitespace-pre-wrap">{report.executive_summary}</p>
          <div className="text-xs text-muted-foreground">
            {payload.model ? <span className="mr-2">model: {payload.model}</span> : null}
            {payload.generated_at ? <span>generated: {payload.generated_at}</span> : null}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Risks</CardTitle>
          </CardHeader>
          <CardContent>
            <BulletList items={report.risks ?? []} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Opportunities</CardTitle>
          </CardHeader>
          <CardContent>
            <BulletList items={report.opportunities ?? []} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recommended Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <BulletList items={report.recommended_actions ?? []} />
          </CardContent>
        </Card>
      </div>

      <div className="space-y-3">
        {report.sections?.map((section) => (
          <Card key={section.name}>
            <CardHeader>
              <CardTitle className="text-base">{section.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p className="whitespace-pre-wrap text-muted-foreground">{section.summary}</p>
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">Insights</p>
                <BulletList items={section.insights ?? []} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {report.references?.length ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">References</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            {report.references.map((ref) => (
              <a
                key={ref}
                className="block truncate text-primary underline-offset-2 hover:underline"
                href={ref}
                target="_blank"
                rel="noreferrer"
              >
                {ref}
              </a>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}

export function CompanyResearchClient() {
  const [companyName, setCompanyName] = useState("")
  const [refresh, setRefresh] = useState(false)

  const startResearch = useStartCompanyResearch()
  const [taskId, setTaskId] = useState<string | null>(null)
  const taskQuery = useTaskStatus(taskId)

  const payload = useMemo(() => {
    if (startResearch.data && !isQueuedResponse(startResearch.data)) {
      return startResearch.data as CompanyResearchPayload
    }
    if (taskQuery.data?.ready && taskQuery.data.result) {
      return normalizeCompanyResearchResult(taskQuery.data.result)
    }
    return null
  }, [startResearch.data, taskQuery.data])

  const isBusy = startResearch.isPending || (Boolean(taskId) && taskQuery.isFetching)

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Company Intelligence</h1>
        <p className="text-muted-foreground">
          Generate a research brief with citations. Runs as a background task when needed.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Research</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
            <div className="space-y-2">
              <Label htmlFor="companyName">Company</Label>
              <Input
                id="companyName"
                placeholder="e.g. Stripe"
                value={companyName}
                onChange={(event) => setCompanyName(event.target.value)}
              />
            </div>
            <Button
              type="button"
              disabled={!companyName.trim() || startResearch.isPending}
              onClick={async () => {
                const name = companyName.trim()
                setTaskId(null)
                try {
                  const result = await startResearch.mutateAsync({ name, refresh })
                  if (isQueuedResponse(result)) {
                    setTaskId(result.task_id)
                    toast.message("Research started in background.")
                  } else {
                    toast.success("Research ready.")
                  }
                } catch (err) {
                  toast.error(err instanceof Error ? err.message : "Failed to start research.")
                }
              }}
            >
              {startResearch.isPending ? "Starting…" : "Generate"}
            </Button>
          </div>

          <div className="flex items-center justify-between gap-3 rounded-lg border bg-background px-3 py-2">
            <div className="space-y-1">
              <p className="text-sm font-medium">Refresh</p>
              <p className="text-xs text-muted-foreground">Bypass cache and re-crawl sources.</p>
            </div>
            <Switch checked={refresh} onCheckedChange={setRefresh} />
          </div>

          {taskId ? (
            <div className="rounded-lg border bg-muted/30 p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">task</span>
                <span className="rounded-full border bg-background px-2 py-0.5 text-xs">
                  {taskId}
                </span>
                <span className="text-xs text-muted-foreground">
                  {taskQuery.data ? taskQuery.data.status : "queued"}
                </span>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {taskQuery.data?.ready ? "Ready." : "Polling until ready…"}
              </p>
              {taskQuery.data?.failed ? (
                <p className="mt-2 text-sm text-destructive">
                  {taskQuery.data.error ?? "Task failed."}
                </p>
              ) : null}
            </div>
          ) : null}

          {startResearch.error ? (
            <p className="text-sm text-destructive">
              {startResearch.error instanceof Error ? startResearch.error.message : "Request failed."}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {isBusy && !payload ? (
        <Card>
          <CardHeader>
            <CardTitle>Generating…</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            This can take a bit while sources are collected and summarized.
          </CardContent>
        </Card>
      ) : null}

      {payload ? <ResearchReport payload={payload} /> : null}
    </div>
  )
}
