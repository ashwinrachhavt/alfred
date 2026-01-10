"use client";

import { useMemo, useState } from "react";

import { toast } from "sonner";

import {
  companyContacts,
  companyInsights,
  companyOutreachGet,
  companyOutreachPost,
  companyOutreachSend,
} from "@/lib/api/company";
import type {
  CompanyContactsResponse,
  CompanyInsightsResponse,
  CompanyOutreachResponse,
  CompanyResearchPayload,
  CompanyResearchQueuedResponse,
  ContactProvider,
  OutreachRequest,
  OutreachSendRequest,
} from "@/lib/api/types/company";
import { useStartCompanyResearch } from "@/features/company/mutations";
import { useCompanyResearchReport } from "@/features/company/queries";
import { useTaskStatus } from "@/features/tasks/queries";
import { useTaskTracker } from "@/features/tasks/task-tracker-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { JsonViewer } from "@/components/ui/json-viewer";

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

  const startResearch = useStartCompanyResearch();
  const { trackTask } = useTaskTracker();
  const [taskId, setTaskId] = useState<string | null>(null);
  const taskQuery = useTaskStatus(taskId);
  const reportQuery = useCompanyResearchReport(reportId ?? null);

  const [insightsRefresh, setInsightsRefresh] = useState(false);
  const [insightsBackground, setInsightsBackground] = useState(false);
  const [insightsRole, setInsightsRole] = useState("");
  const [insightsTaskId, setInsightsTaskId] = useState<string | null>(null);
  const insightsTaskQuery = useTaskStatus(insightsTaskId);
  const [insightsResult, setInsightsResult] = useState<CompanyInsightsResponse | null>(null);

  const [outreachRole, setOutreachRole] = useState("AI Engineer");
  const [useOutreachPost, setUseOutreachPost] = useState(false);
  const [outreachContext, setOutreachContext] = useState("");
  const [outreachK, setOutreachK] = useState<string>("");
  const [outreachResult, setOutreachResult] = useState<CompanyOutreachResponse | null>(null);

  const [contactsRole, setContactsRole] = useState("");
  const [contactsLimit, setContactsLimit] = useState(20);
  const [contactsRefresh, setContactsRefresh] = useState(false);
  const [contactsProviders, setContactsProviders] = useState<string>("");
  const [contactsResult, setContactsResult] = useState<CompanyContactsResponse | null>(null);

  const [sendDialogOpen, setSendDialogOpen] = useState(false);
  const [sendRequest, setSendRequest] = useState<OutreachSendRequest>({
    company: "",
    contact_email: "",
    contact_name: "",
    contact_title: "",
    subject: "",
    body: "",
    dry_run: true,
  });
  const [sendResult, setSendResult] = useState<Record<string, unknown> | null>(null);
  const [sendBusy, setSendBusy] = useState(false);

  const companyFromReport = useMemo(() => {
    const normalized = reportQuery.data ? normalizeCompanyResearchResult(reportQuery.data) : null;
    return normalized?.company ?? "";
  }, [reportQuery.data]);

  const effectiveCompanyName = hasEditedCompanyName
    ? companyName
    : companyName || companyFromReport;

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

  const effectiveCompany = effectiveCompanyName.trim();

  const insightsPayload = useMemo(() => {
    if (insightsTaskQuery.data?.ready && insightsTaskQuery.data.result) {
      return insightsTaskQuery.data.result as CompanyInsightsResponse;
    }
    return insightsResult;
  }, [insightsResult, insightsTaskQuery.data]);

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
          <CardTitle>Company</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <div className="space-y-2">
            <Label htmlFor="companyName">Company</Label>
            <Input
              id="companyName"
              placeholder="e.g. Stripe"
              value={effectiveCompanyName}
              onChange={(event) => {
                if (!hasEditedCompanyName) setHasEditedCompanyName(true);
                setCompanyName(event.target.value);
                setSendRequest((prev) => ({ ...prev, company: event.target.value }));
              }}
            />
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <Button asChild variant="outline" type="button">
              <a href={`/company?reportId=${reportId ?? ""}`}>Reload</a>
            </Button>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="research">
        <TabsList>
          <TabsTrigger value="research">Research</TabsTrigger>
          <TabsTrigger value="insights">Insights</TabsTrigger>
          <TabsTrigger value="outreach">Outreach</TabsTrigger>
          <TabsTrigger value="contacts">Contacts</TabsTrigger>
          <TabsTrigger value="send">Send</TabsTrigger>
        </TabsList>

        <TabsContent value="research" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Research</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-background flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Refresh</p>
                  <p className="text-muted-foreground text-xs">Bypass cache and re-crawl sources.</p>
                </div>
                <Switch checked={refresh} onCheckedChange={setRefresh} />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  disabled={!effectiveCompany || startResearch.isPending}
                  onClick={async () => {
                    const name = effectiveCompany;
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
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => reportQuery.refetch()}
                  disabled={reportQuery.isFetching}
                >
                  Refresh saved report
                </Button>
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
        </TabsContent>

        <TabsContent value="insights" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Insights</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="insightsRole">Role (optional)</Label>
                  <Input
                    id="insightsRole"
                    value={insightsRole}
                    onChange={(e) => setInsightsRole(e.target.value)}
                    placeholder="e.g. Staff Engineer"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Company</Label>
                  <Input value={effectiveCompany} readOnly />
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="bg-background flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
                  <div className="space-y-1">
                    <p className="text-sm font-medium">Refresh</p>
                    <p className="text-muted-foreground text-xs">Force a re-fetch + regeneration.</p>
                  </div>
                  <Switch checked={insightsRefresh} onCheckedChange={setInsightsRefresh} />
                </div>
                <div className="bg-background flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
                  <div className="space-y-1">
                    <p className="text-sm font-medium">Background</p>
                    <p className="text-muted-foreground text-xs">Enqueue instead of blocking.</p>
                  </div>
                  <Switch checked={insightsBackground} onCheckedChange={setInsightsBackground} />
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  disabled={!effectiveCompany}
                  onClick={async () => {
                    setInsightsResult(null);
                    setInsightsTaskId(null);
                    try {
                      const res = await companyInsights({
                        name: effectiveCompany,
                        role: insightsRole.trim() || null,
                        refresh: insightsRefresh,
                        background: insightsBackground,
                      });
                      if (isQueuedResponse(res)) {
                        setInsightsTaskId(res.task_id);
                        trackTask({
                          id: res.task_id,
                          source: "company_insights",
                          label: `Company insights: ${effectiveCompany}`,
                          href: "/company",
                        });
                        toast.message("Insights enqueued.");
                      } else {
                        setInsightsResult(res);
                        toast.success("Insights ready.");
                      }
                    } catch (err) {
                      toast.error(err instanceof Error ? err.message : "Failed to fetch insights.");
                    }
                  }}
                >
                  Generate insights
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setInsightsResult(null)}
                >
                  Clear
                </Button>
              </div>

              {insightsTaskId ? (
                <div className="bg-muted/30 rounded-lg border p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">task</span>
                    <span className="bg-background rounded-full border px-2 py-0.5 text-xs">
                      {insightsTaskId}
                    </span>
                    <span className="text-muted-foreground text-xs">
                      {insightsTaskQuery.data ? insightsTaskQuery.data.status : "queued"}
                    </span>
                  </div>
                  <p className="text-muted-foreground mt-2 text-xs">
                    {insightsTaskQuery.data?.ready ? "Ready." : "Polling until ready…"}
                  </p>
                  {insightsTaskQuery.data?.failed ? (
                    <p className="text-destructive mt-2 text-sm">
                      {insightsTaskQuery.data.error ?? "Task failed."}
                    </p>
                  ) : null}
                </div>
              ) : null}

              {insightsPayload ? <JsonViewer value={insightsPayload} title="Insights response" /> : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="outreach" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Outreach</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="outreachRole">Role / angle</Label>
                  <Input
                    id="outreachRole"
                    value={outreachRole}
                    onChange={(e) => setOutreachRole(e.target.value)}
                  />
                </div>
                <div className="bg-background flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
                  <div className="space-y-1">
                    <p className="text-sm font-medium">Use POST</p>
                    <p className="text-muted-foreground text-xs">
                      Enables extra context + retrieval parameter.
                    </p>
                  </div>
                  <Switch checked={useOutreachPost} onCheckedChange={setUseOutreachPost} />
                </div>
              </div>

              {useOutreachPost ? (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="outreachContext">Context (optional)</Label>
                    <Textarea
                      id="outreachContext"
                      value={outreachContext}
                      onChange={(e) => setOutreachContext(e.target.value)}
                      rows={4}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="outreachK">k (optional)</Label>
                    <Input
                      id="outreachK"
                      inputMode="numeric"
                      value={outreachK}
                      onChange={(e) => setOutreachK(e.target.value)}
                      placeholder="e.g. 6"
                    />
                  </div>
                </div>
              ) : null}

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  disabled={!effectiveCompany}
                  onClick={async () => {
                    setOutreachResult(null);
                    try {
                      if (!useOutreachPost) {
                        const res = await companyOutreachGet({
                          name: effectiveCompany,
                          role: outreachRole.trim() || "AI Engineer",
                        });
                        setOutreachResult(res);
                        toast.success("Outreach ready.");
                        return;
                      }

                      const kParsed = Number(outreachK.trim());
                      const payload: OutreachRequest = {
                        name: effectiveCompany,
                        role: outreachRole.trim() || "AI Engineer",
                        context: outreachContext.trim() || null,
                        k: outreachK.trim() && Number.isFinite(kParsed) ? kParsed : null,
                      };
                      const res = await companyOutreachPost(payload);
                      setOutreachResult(res);
                      toast.success("Outreach ready.");
                    } catch (err) {
                      toast.error(err instanceof Error ? err.message : "Failed to generate outreach.");
                    }
                  }}
                >
                  Generate outreach
                </Button>
                <Button type="button" variant="outline" onClick={() => setOutreachResult(null)}>
                  Clear
                </Button>
              </div>

              {outreachResult ? <JsonViewer value={outreachResult} title="Outreach response" /> : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="contacts" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Contacts</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="contactsRole">Role/title filter (optional)</Label>
                  <Input
                    id="contactsRole"
                    value={contactsRole}
                    onChange={(e) => setContactsRole(e.target.value)}
                    placeholder="e.g. engineering"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="contactsProviders">Providers (comma-separated)</Label>
                  <Input
                    id="contactsProviders"
                    value={contactsProviders}
                    onChange={(e) => setContactsProviders(e.target.value)}
                    placeholder="hunter, apollo, snov"
                  />
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="contactsLimit">Limit</Label>
                  <Input
                    id="contactsLimit"
                    inputMode="numeric"
                    value={String(contactsLimit)}
                    onChange={(e) => setContactsLimit(Number(e.target.value))}
                  />
                </div>
                <div className="bg-background flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
                  <div className="space-y-1">
                    <p className="text-sm font-medium">Refresh</p>
                    <p className="text-muted-foreground text-xs">Force refresh from providers.</p>
                  </div>
                  <Switch checked={contactsRefresh} onCheckedChange={setContactsRefresh} />
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  disabled={!effectiveCompany}
                  onClick={async () => {
                    setContactsResult(null);
                    try {
                      const providers = contactsProviders
                        .split(",")
                        .map((p) => p.trim())
                        .filter(Boolean) as ContactProvider[];
                      const res = await companyContacts({
                        name: effectiveCompany,
                        role: contactsRole.trim() || null,
                        limit: Math.max(1, Math.min(50, contactsLimit)),
                        refresh: contactsRefresh,
                        providers: providers.length ? providers : null,
                      });
                      setContactsResult(res);
                      toast.success("Contacts ready.");
                    } catch (err) {
                      toast.error(err instanceof Error ? err.message : "Failed to fetch contacts.");
                    }
                  }}
                >
                  Fetch contacts
                </Button>
                <Button type="button" variant="outline" onClick={() => setContactsResult(null)}>
                  Clear
                </Button>
              </div>

              {contactsResult ? <JsonViewer value={contactsResult} title="Contacts response" /> : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="send" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Send outreach email</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-background flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Dry run</p>
                  <p className="text-muted-foreground text-xs">
                    When enabled, backend should not send; only logs.
                  </p>
                </div>
                <Switch
                  checked={Boolean(sendRequest.dry_run)}
                  onCheckedChange={(next) =>
                    setSendRequest((prev) => ({ ...prev, dry_run: next }))
                  }
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="sendCompany">Company</Label>
                  <Input
                    id="sendCompany"
                    value={sendRequest.company}
                    onChange={(e) =>
                      setSendRequest((prev) => ({ ...prev, company: e.target.value }))
                    }
                    placeholder={effectiveCompany || "Company"}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sendEmail">Contact email</Label>
                  <Input
                    id="sendEmail"
                    value={sendRequest.contact_email}
                    onChange={(e) =>
                      setSendRequest((prev) => ({ ...prev, contact_email: e.target.value }))
                    }
                    placeholder="person@company.com"
                  />
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="sendName">Contact name (optional)</Label>
                  <Input
                    id="sendName"
                    value={sendRequest.contact_name ?? ""}
                    onChange={(e) =>
                      setSendRequest((prev) => ({ ...prev, contact_name: e.target.value }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sendTitle">Contact title (optional)</Label>
                  <Input
                    id="sendTitle"
                    value={sendRequest.contact_title ?? ""}
                    onChange={(e) =>
                      setSendRequest((prev) => ({ ...prev, contact_title: e.target.value }))
                    }
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="sendSubject">Subject</Label>
                <Input
                  id="sendSubject"
                  value={sendRequest.subject}
                  onChange={(e) =>
                    setSendRequest((prev) => ({ ...prev, subject: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sendBody">Body</Label>
                <Textarea
                  id="sendBody"
                  value={sendRequest.body}
                  onChange={(e) =>
                    setSendRequest((prev) => ({ ...prev, body: e.target.value }))
                  }
                  rows={8}
                />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  onClick={() => setSendDialogOpen(true)}
                  disabled={sendBusy || !sendRequest.company.trim() || !sendRequest.contact_email.trim() || !sendRequest.subject.trim() || !sendRequest.body.trim()}
                >
                  Send
                </Button>
                <Button type="button" variant="outline" onClick={() => setSendResult(null)}>
                  Clear result
                </Button>
              </div>

              {sendResult ? <JsonViewer value={sendResult} title="Send response" collapsed /> : null}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={sendDialogOpen} onOpenChange={setSendDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {sendRequest.dry_run ? "Run outreach send dry-run?" : "Send outreach email?"}
            </DialogTitle>
            <DialogDescription>
              {sendRequest.dry_run
                ? "This should not send email. It only logs the payload on the server."
                : "This will send a real email using server credentials."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 rounded-lg border p-3 text-sm">
            <p>
              <span className="text-muted-foreground">company:</span>{" "}
              {sendRequest.company.trim() || "—"}
            </p>
            <p>
              <span className="text-muted-foreground">to:</span>{" "}
              {sendRequest.contact_email.trim() || "—"}
            </p>
            <p>
              <span className="text-muted-foreground">subject:</span>{" "}
              {sendRequest.subject.trim() || "—"}
            </p>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setSendDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              onClick={async () => {
                setSendBusy(true);
                setSendDialogOpen(false);
                try {
                  const payload: OutreachSendRequest = {
                    ...sendRequest,
                    company: sendRequest.company.trim() || effectiveCompany,
                    contact_email: sendRequest.contact_email.trim(),
                    subject: sendRequest.subject.trim(),
                    body: sendRequest.body,
                    contact_name: sendRequest.contact_name?.trim() || null,
                    contact_title: sendRequest.contact_title?.trim() || null,
                    dry_run: Boolean(sendRequest.dry_run),
                  };
                  const res = await companyOutreachSend(payload);
                  setSendResult(res);
                  toast.success(sendRequest.dry_run ? "Dry run complete." : "Sent.");
                } catch (err) {
                  toast.error(err instanceof Error ? err.message : "Send failed.");
                } finally {
                  setSendBusy(false);
                }
              }}
              disabled={sendBusy}
            >
              {sendBusy ? "Working…" : sendRequest.dry_run ? "Continue" : "Send"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
