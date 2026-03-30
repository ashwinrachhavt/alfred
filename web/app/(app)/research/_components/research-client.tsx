"use client";

import { useRouter } from "next/navigation";
import { memo, useCallback, useMemo, useState } from "react";

import { BookOpen, Clock, Plus, RefreshCw, Search, Sparkles } from "lucide-react";
import { toast } from "sonner";

import type {
  ResearchPayload,
  ResearchQueuedResponse,
  ResearchReportSummary,
} from "@/lib/api/types/research";
import { useStartDeepResearch } from "@/features/research/mutations";
import {
  useRecentResearchReports,
  useResearchReport,
} from "@/features/research/queries";
import { useTaskTracker } from "@/features/tasks/task-tracker-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isQueuedResponse(value: unknown): value is ResearchQueuedResponse {
  return (
    value !== null && typeof value === "object" && "task_id" in value && "status_url" in value
  );
}

function normalizeResearchResult(value: unknown): ResearchPayload | null {
  if (!value || typeof value !== "object") return null;
  if (!("report" in value)) return null;
  return value as ResearchPayload;
}

function formatRelativeDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ---------------------------------------------------------------------------
// Report List Item
// ---------------------------------------------------------------------------

const ReportListItem = memo(function ReportListItem({
  report,
  isActive,
  onSelect,
}: {
  report: ResearchReportSummary;
  isActive: boolean;
  onSelect: (id: string) => void;
}) {
  const handleClick = useCallback(
    () => onSelect(report.id),
    [onSelect, report.id],
  );
  const topic = report.topic ?? report.company ?? "Untitled";
  const summary = report.executive_summary;
  const truncatedSummary = summary && summary.length > 120 ? summary.slice(0, 120) + "..." : summary;

  return (
    <button
      type="button"
      onClick={handleClick}
      className={cn(
        "w-full rounded-lg border px-3 py-3 text-left transition-colors",
        isActive
          ? "border-primary/30 bg-primary/5"
          : "border-transparent hover:bg-muted/50"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-medium leading-snug">{topic}</h3>
        <span className="text-muted-foreground mt-0.5 shrink-0 text-[11px]">
          {formatRelativeDate(report.generated_at ?? report.updated_at)}
        </span>
      </div>
      {truncatedSummary ? (
        <p className="text-muted-foreground mt-1 line-clamp-2 text-xs leading-relaxed">
          {truncatedSummary}
        </p>
      ) : null}
      {report.model_name ? (
        <Badge variant="outline" className="mt-1.5 text-[10px]">
          {report.model_name}
        </Badge>
      ) : null}
    </button>
  );
});

// ---------------------------------------------------------------------------
// Report Thread List (left panel)
// ---------------------------------------------------------------------------

function ReportThreadList({
  selectedId,
  onSelect,
  onNewResearch,
}: {
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNewResearch: () => void;
}) {
  const reportsQuery = useRecentResearchReports(50);
  const reports = reportsQuery.data ?? [];
  const [search, setSearch] = useState("");

  const handleReportSelect = useCallback(
    (reportId: string) => {
      onSelect(reportId);
    },
    [onSelect],
  );

  const filtered = useMemo(() => {
    if (!search.trim()) return reports;
    const q = search.toLowerCase();
    return reports.filter((r) => {
      const topic = (r.topic ?? r.company ?? "").toLowerCase();
      const summary = (r.executive_summary ?? "").toLowerCase();
      return topic.includes(q) || summary.includes(q);
    });
  }, [reports, search]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <h2 className="font-serif text-lg tracking-tight">Research</h2>
        <Button size="sm" variant="ghost" onClick={onNewResearch}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          New
        </Button>
      </div>

      <div className="px-4 pb-2">
        <div className="relative">
          <Search className="text-muted-foreground absolute left-2.5 top-2.5 h-3.5 w-3.5" />
          <Input
            placeholder="Search reports..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 pl-8 text-xs"
          />
        </div>
      </div>

      <Separator />

      <div className="flex-1 space-y-1 overflow-y-auto px-3 py-2">
        {reportsQuery.isLoading ? (
          <div className="space-y-3 px-1 py-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="space-y-1.5">
                <div className="bg-muted h-4 w-3/4 animate-pulse rounded" />
                <div className="bg-muted h-3 w-full animate-pulse rounded" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <BookOpen className="text-muted-foreground/50 mb-3 h-8 w-8" />
            <p className="text-muted-foreground text-sm">
              {search ? "No matching reports" : "No research yet"}
            </p>
            <p className="text-muted-foreground mt-1 text-xs">
              {search ? "Try a different search term" : "Generate your first report above"}
            </p>
          </div>
        ) : (
          filtered.map((report) => (
            <ReportListItem
              key={report.id}
              report={report}
              isActive={selectedId === report.id}
              onSelect={handleReportSelect}
            />
          ))
        )}
      </div>

      {reports.length > 0 ? (
        <>
          <Separator />
          <div className="text-muted-foreground px-4 py-2 text-center text-[11px]">
            {reports.length} report{reports.length === 1 ? "" : "s"}
          </div>
        </>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bullet List
// ---------------------------------------------------------------------------

function BulletList({ items }: { items: string[] }) {
  if (!items.length) return <p className="text-muted-foreground text-sm">None identified.</p>;
  return (
    <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed">
      {items.map((item, idx) => (
        <li key={`${idx}-${item.slice(0, 16)}`}>{item}</li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Full Report View (right panel)
// ---------------------------------------------------------------------------

function ResearchReportView({ payload }: { payload: ResearchPayload }) {
  const report = payload.report;
  const topic = payload.topic ?? payload.company ?? "Research Report";

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-serif text-2xl tracking-tight">{topic}</h1>
        <div className="text-muted-foreground mt-1 flex items-center gap-3 text-xs">
          {payload.model ? (
            <span className="flex items-center gap-1">
              <Sparkles className="h-3 w-3" />
              {payload.model}
            </span>
          ) : null}
          {payload.generated_at ? (
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {new Date(payload.generated_at).toLocaleString()}
            </span>
          ) : null}
          {payload.sources?.length ? (
            <span>{payload.sources.length} sources</span>
          ) : null}
        </div>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Executive Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">
            {report.executive_summary}
          </p>
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

      <div className="space-y-4">
        {report.sections?.map((section) => (
          <Card key={section.name}>
            <CardHeader>
              <CardTitle className="text-base">{section.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p className="text-muted-foreground leading-relaxed whitespace-pre-wrap">
                {section.summary}
              </p>
              <div>
                <p className="text-muted-foreground mb-2 text-xs font-medium uppercase tracking-wider">
                  Insights
                </p>
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
            {report.references.map((ref, idx) => (
              <a
                key={`${idx}-${ref}`}
                className="text-primary block truncate underline-offset-2 hover:underline"
                href={ref.startsWith("http") ? ref : undefined}
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

// ---------------------------------------------------------------------------
// New Research Form
// ---------------------------------------------------------------------------

function NewResearchForm({ onGenerated }: { onGenerated: () => void }) {
  const [topic, setTopic] = useState("");
  const [refresh, setRefresh] = useState(false);
  const startResearch = useStartDeepResearch();
  const { trackTask } = useTaskTracker();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-4 w-4" />
          New Research
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <div className="space-y-2">
            <Label htmlFor="researchTopic">Topic</Label>
            <Input
              id="researchTopic"
              placeholder="e.g. Transformer architecture, Stoicism, quantum computing"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && topic.trim() && !startResearch.isPending) {
                  e.preventDefault();
                  document.getElementById("researchGenerate")?.click();
                }
              }}
            />
          </div>
          <Button
            id="researchGenerate"
            type="button"
            disabled={!topic.trim() || startResearch.isPending}
            onClick={async () => {
              const name = topic.trim();
              try {
                const result = await startResearch.mutateAsync({
                  topic: name,
                  refresh,
                });
                if (isQueuedResponse(result)) {
                  trackTask({
                    id: result.task_id,
                    source: "company_research",
                    label: `Research: ${name}`,
                  });
                  toast.message(`Research queued: ${name}`);
                } else {
                  toast.success("Research ready.");
                  onGenerated();
                }
                setTopic("");
              } catch (err) {
                toast.error(
                  err instanceof Error ? err.message : "Failed to start research."
                );
              }
            }}
          >
            {startResearch.isPending ? (
              <>
                <RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                Starting...
              </>
            ) : (
              "Generate"
            )}
          </Button>
        </div>

        <div className="bg-background flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
          <div className="space-y-0.5">
            <p className="text-sm font-medium">Refresh</p>
            <p className="text-muted-foreground text-xs">Bypass cache and re-crawl sources.</p>
          </div>
          <Switch checked={refresh} onCheckedChange={setRefresh} />
        </div>

        {startResearch.error ? (
          <p className="text-destructive text-sm">
            {startResearch.error instanceof Error
              ? startResearch.error.message
              : "Request failed."}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------

function EmptyReportState({ onNewResearch }: { onNewResearch: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center text-center">
      <BookOpen className="text-muted-foreground/30 mb-4 h-12 w-12" />
      <h2 className="font-serif text-xl">Select a report</h2>
      <p className="text-muted-foreground mt-1 max-w-sm text-sm">
        Pick a report from the list, or generate a new one to get started.
      </p>
      <Button variant="outline" className="mt-4" onClick={onNewResearch}>
        <Plus className="mr-1.5 h-3.5 w-3.5" />
        New Research
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Client
// ---------------------------------------------------------------------------

type ResearchClientProps = {
  reportId?: string;
  initialTopic?: string;
  initialRefresh?: boolean;
};

export function ResearchClient({ reportId }: ResearchClientProps) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<string | null>(reportId ?? null);
  const [showNewForm, setShowNewForm] = useState(false);

  const reportQuery = useResearchReport(selectedId);
  const payload = useMemo(() => {
    if (!reportQuery.data) return null;
    return normalizeResearchResult(reportQuery.data);
  }, [reportQuery.data]);

  const handleSelect = (id: string) => {
    setSelectedId(id);
    setShowNewForm(false);
    router.push(`/research?reportId=${encodeURIComponent(id)}`, { scroll: false });
  };

  const handleNewResearch = () => {
    setShowNewForm(true);
    setSelectedId(null);
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] gap-0">
      {/* Left panel: report list */}
      <div className="border-r w-80 shrink-0 overflow-hidden">
        <ReportThreadList
          selectedId={selectedId}
          onSelect={handleSelect}
          onNewResearch={handleNewResearch}
        />
      </div>

      {/* Right panel: report detail or new form */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {showNewForm ? (
          <div className="mx-auto max-w-4xl space-y-6">
            <NewResearchForm
              onGenerated={() => {
                setShowNewForm(false);
              }}
            />
          </div>
        ) : reportQuery.isLoading && selectedId ? (
          <div className="flex h-full items-center justify-center">
            <div className="space-y-3 text-center">
              <RefreshCw className="text-muted-foreground mx-auto h-6 w-6 animate-spin" />
              <p className="text-muted-foreground text-sm">Loading report...</p>
            </div>
          </div>
        ) : payload ? (
          <div className="mx-auto max-w-4xl">
            <ResearchReportView payload={payload} />
          </div>
        ) : (
          <EmptyReportState onNewResearch={handleNewResearch} />
        )}
      </div>
    </div>
  );
}
