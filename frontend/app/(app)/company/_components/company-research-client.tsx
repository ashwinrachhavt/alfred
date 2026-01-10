"use client";

import { useMemo, useState } from "react";

import { toast } from "sonner";

import type {
  CompanyResearchPayload,
  CompanyResearchQueuedResponse,
} from "@/lib/api/types/company";
import { useDiscoverCompanyContacts, useStartCompanyResearch } from "@/features/company/mutations";
import { useCompanyContactsFromDb, useCompanyResearchReport } from "@/features/company/queries";
import { useTaskStatus } from "@/features/tasks/queries";
import { useTaskTracker } from "@/features/tasks/task-tracker-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

function isQueuedResponse(value: unknown): value is CompanyResearchQueuedResponse {
  return value !== null && typeof value === "object" && "task_id" in value && "status_url" in value;
}

function normalizeCompanyResearchResult(value: unknown): CompanyResearchPayload | null {
  if (!value || typeof value !== "object") return null;
  if (!("report" in value)) return null;
  return value as CompanyResearchPayload;
}

function BulletList({ items }: { items: string[] }) {
  if (!items.length) return <p className="text-muted-foreground text-sm">—</p>;
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm">
      {items.map((item, idx) => (
        <li key={`${idx}-${item.slice(0, 16)}`}>{item}</li>
      ))}
    </ul>
  );
}

function ResearchReport({ payload }: { payload: CompanyResearchPayload }) {
  const report = payload.report;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Executive Summary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="whitespace-pre-wrap">{report.executive_summary}</p>
          <div className="text-muted-foreground text-xs">
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
              <p className="text-muted-foreground whitespace-pre-wrap">{section.summary}</p>
              <div>
                <p className="text-muted-foreground mb-2 text-xs font-medium">Insights</p>
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
                className="text-primary block truncate underline-offset-2 hover:underline"
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
  );
}

type CompanyResearchClientProps = {
  reportId?: string;
};

export function CompanyResearchClient({ reportId }: CompanyResearchClientProps) {
  const [companyName, setCompanyName] = useState("");
  const [hasEditedCompanyName, setHasEditedCompanyName] = useState(false);
  const [refresh, setRefresh] = useState(false);
  const [contactsRole, setContactsRole] = useState("");

  const startResearch = useStartCompanyResearch();
  const discoverContacts = useDiscoverCompanyContacts();
  const { trackTask } = useTaskTracker();
  const [taskId, setTaskId] = useState<string | null>(null);
  const taskQuery = useTaskStatus(taskId);
  const reportQuery = useCompanyResearchReport(reportId ?? null);

  const companyFromReport = useMemo(() => {
    const normalized = reportQuery.data ? normalizeCompanyResearchResult(reportQuery.data) : null;
    return normalized?.company ?? "";
  }, [reportQuery.data]);

  const effectiveCompanyName = hasEditedCompanyName
    ? companyName
    : companyName || companyFromReport;
  const trimmedCompanyName = effectiveCompanyName.trim();

  const contactsQuery = useCompanyContactsFromDb({
    name: trimmedCompanyName,
    role: contactsRole || undefined,
    limit: 20,
  });

  const payload = useMemo(() => {
    if (startResearch.data && !isQueuedResponse(startResearch.data)) {
      return startResearch.data as CompanyResearchPayload;
    }
    if (taskQuery.data?.ready && taskQuery.data.result) {
      return normalizeCompanyResearchResult(taskQuery.data.result);
    }
    if (reportQuery.data) {
      return normalizeCompanyResearchResult(reportQuery.data);
    }
    return null;
  }, [startResearch.data, taskQuery.data, reportQuery.data]);

  const isBusy =
    reportQuery.isFetching || startResearch.isPending || (Boolean(taskId) && taskQuery.isFetching);

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
                value={effectiveCompanyName}
                onChange={(event) => {
                  if (!hasEditedCompanyName) setHasEditedCompanyName(true);
                  setCompanyName(event.target.value);
                }}
              />
            </div>
            <Button
              type="button"
              disabled={!trimmedCompanyName || startResearch.isPending}
              onClick={async () => {
                const name = trimmedCompanyName;
                setTaskId(null);
                try {
                  const result = await startResearch.mutateAsync({ name, refresh });
                  if (isQueuedResponse(result)) {
                    setTaskId(result.task_id);
                    trackTask({
                      id: result.task_id,
                      source: "company_research",
                      label: `Company research: ${name}`,
                    });
                    toast.message("Research started in background.");
                  } else {
                    toast.success("Research ready.");
                  }
                } catch (err) {
                  toast.error(err instanceof Error ? err.message : "Failed to start research.");
                }
              }}
            >
              {startResearch.isPending ? "Starting…" : "Generate"}
            </Button>
          </div>

          <div className="bg-background flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
            <div className="space-y-1">
              <p className="text-sm font-medium">Refresh</p>
              <p className="text-muted-foreground text-xs">Bypass cache and re-crawl sources.</p>
            </div>
            <Switch checked={refresh} onCheckedChange={setRefresh} />
          </div>

          {taskId ? (
            <div className="bg-muted/30 rounded-lg border p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">task</span>
                <span className="bg-background rounded-full border px-2 py-0.5 text-xs">
                  {taskId}
                </span>
                <span className="text-muted-foreground text-xs">
                  {taskQuery.data ? taskQuery.data.status : "queued"}
                </span>
              </div>
              <p className="text-muted-foreground mt-2 text-xs">
                {taskQuery.data?.ready ? "Ready." : "Polling until ready…"}
              </p>
              {taskQuery.data?.failed ? (
                <p className="text-destructive mt-2 text-sm">
                  {taskQuery.data.error ?? "Task failed."}
                </p>
              ) : null}
            </div>
          ) : null}

          {reportQuery.isError ? (
            <p className="text-destructive text-sm">
              {reportQuery.error instanceof Error
                ? reportQuery.error.message
                : "Failed to load report."}
            </p>
          ) : null}

          {startResearch.error ? (
            <p className="text-destructive text-sm">
              {startResearch.error instanceof Error
                ? startResearch.error.message
                : "Request failed."}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <CardTitle>Contacts</CardTitle>
            <p className="text-muted-foreground text-sm">
              Contacts saved in the database for this company.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={discoverContacts.isPending || !trimmedCompanyName}
            onClick={async () => {
              if (!trimmedCompanyName) return;
              try {
                await discoverContacts.mutateAsync({
                  name: trimmedCompanyName,
                  role: contactsRole || undefined,
                });
                await contactsQuery.refetch();
                toast.success("Contact discovery complete.");
              } catch (err) {
                toast.error(
                  err instanceof Error ? err.message : "Failed to discover contacts from providers.",
                );
              }
            }}
          >
            {discoverContacts.isPending ? "Discovering…" : "Discover contacts"}
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
            <div className="space-y-2">
              <Label htmlFor="contactsRole">Role filter</Label>
              <Input
                id="contactsRole"
                placeholder="e.g. engineering"
                value={contactsRole}
                disabled={!trimmedCompanyName}
                onChange={(event) => setContactsRole(event.target.value)}
              />
            </div>
            <Button
              type="button"
              variant="secondary"
              disabled={contactsQuery.isFetching || !trimmedCompanyName}
              onClick={() => contactsQuery.refetch()}
            >
              {contactsQuery.isFetching ? "Refreshing…" : "Refresh list"}
            </Button>
          </div>

          {!trimmedCompanyName ? (
            <EmptyState
              title="Enter a company to load contacts"
              description="Type a company name above, then refresh or discover contacts."
            />
          ) : null}

          {contactsQuery.isError ? (
            <p className="text-destructive text-sm">
              {contactsQuery.error instanceof Error
                ? contactsQuery.error.message
                : "Failed to load contacts."}
            </p>
          ) : null}

          {contactsQuery.isFetching && !contactsQuery.data ? (
            <p className="text-muted-foreground text-sm">Loading contacts…</p>
          ) : null}

          {contactsQuery.data?.items?.length ? (
            <div className="overflow-hidden rounded-lg border">
              <div className="bg-muted/30 grid grid-cols-[1fr_1fr_1fr_auto] gap-3 px-3 py-2 text-xs font-medium">
                <span>Name</span>
                <span>Title</span>
                <span>Email</span>
                <span className="text-right">Meta</span>
              </div>
              <div className="divide-y">
                {contactsQuery.data.items.map((item) => {
                  const confidencePct = Math.round((item.confidence ?? 0) * 100);
                  const createdAt = item.created_at ? new Date(item.created_at) : null;
                  return (
                    <div
                      key={`${item.id ?? "row"}-${item.email}`}
                      className="grid grid-cols-[1fr_1fr_1fr_auto] gap-3 px-3 py-3 text-sm"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium">{item.name || "—"}</p>
                        <p className="text-muted-foreground truncate text-xs">{item.company}</p>
                      </div>
                      <p className="text-muted-foreground line-clamp-2">{item.title || "—"}</p>
                      <a
                        className="text-primary truncate underline-offset-2 hover:underline"
                        href={`mailto:${item.email}`}
                      >
                        {item.email || "—"}
                      </a>
                      <div className="flex items-center justify-end gap-2">
                        <Badge variant="outline">{item.source || "unknown"}</Badge>
                        <Badge variant="secondary">{confidencePct}%</Badge>
                        <span className="text-muted-foreground hidden text-xs sm:inline">
                          {createdAt ? createdAt.toLocaleDateString() : "—"}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : contactsQuery.data && trimmedCompanyName ? (
            <EmptyState
              title="No saved contacts yet"
              description="Discover contacts (if provider keys are configured) or run outreach to populate the table."
            />
          ) : null}
        </CardContent>
      </Card>

      {reportQuery.isFetching && !payload ? (
        <Card>
          <CardHeader>
            <CardTitle>Loading report…</CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground text-sm">
            Fetching a saved research report.
          </CardContent>
        </Card>
      ) : null}

      {isBusy && !payload && !reportQuery.isFetching ? (
        <Card>
          <CardHeader>
            <CardTitle>Generating…</CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground text-sm">
            This can take a bit while sources are collected and summarized.
          </CardContent>
        </Card>
      ) : null}

      {payload ? <ResearchReport payload={payload} /> : null}
    </div>
  );
}
