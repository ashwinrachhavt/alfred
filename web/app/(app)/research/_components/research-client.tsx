"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  FileText,
  FileSearch,
  FilesIcon,
  Globe2,
  History,
  Library,
  ListTodo,
  Loader2,
  Play,
  Save,
  Settings as SettingsIcon,
  Sparkles,
  Square,
} from "lucide-react";
import { toast } from "sonner";

import { MessageResponse } from "@/components/ai-elements/message";
import { Shimmer } from "@/components/ai-elements/shimmer";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  researchReportQueryKey,
  useRecentResearchReports,
  useResearchReport,
} from "@/features/research/queries";
import { useResearchAgents } from "@/features/research-agents/queries";
import type { ResearchReportSummary } from "@/lib/api/types/research";
import type { ResearchAgentSpec } from "@/lib/api/research-agents";
import type { DeepToolCall } from "@/lib/stores/research-store";
import {
  useResearchActions,
  useResearchMainStream,
  useResearchReportId,
  useResearchRunState,
} from "@/lib/stores/research-store";

import { FilesPanel } from "./files-panel";
import { PlanPanel } from "./plan-panel";
import { SubagentLanes } from "./subagent-lanes";

const EXAMPLE_PROMPTS = [
  "Map the market for AI tools built for philosophers and polymaths.",
  "Compare NotebookLM, Elicit, Perplexity, Obsidian, and Readwise for deep thinkers.",
  "Find the product wedge for Polymath AI as a knowledge portal.",
];

const CAPABILITY_BADGES = [
  { label: "Web", icon: Globe2 },
  { label: "Papers", icon: FileSearch },
  { label: "KB", icon: Library },
  { label: "Synthesis", icon: BrainCircuit },
];

function reportTitle(report: ResearchReportSummary) {
  return report.topic ?? report.company ?? "Untitled report";
}

function formatReportTime(value?: string | null) {
  if (!value) return "Unknown";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
}

function toolState(
  status: DeepToolCall["status"],
): "input-available" | "output-available" | "output-error" {
  if (status === "done") return "output-available";
  if (status === "error") return "output-error";
  return "input-available";
}

function ResearchToolCall({ call }: { call: DeepToolCall }) {
  return (
    <Tool
      defaultOpen={call.status !== "done"}
      className="mb-2 border-border/70 bg-background/45"
    >
      <ToolHeader
        type="dynamic-tool"
        toolName={call.tool}
        state={toolState(call.status)}
        className="px-3 py-2"
      />
      <ToolContent className="border-t border-border/50 px-3 py-3">
        <ToolInput input={call.args} />
        <ToolOutput
          output={call.result}
          errorText={call.status === "error" ? "Tool failed" : undefined}
        />
      </ToolContent>
    </Tool>
  );
}

function AgentPicker({
  specs,
  value,
  onChange,
}: {
  specs: ResearchAgentSpec[];
  value: number | null;
  onChange: (id: number) => void;
}) {
  return (
    <Select
      value={value !== null ? String(value) : ""}
      onValueChange={(v) => onChange(Number(v))}
    >
      <SelectTrigger className="h-11 w-full min-w-0 rounded-md border-border/80 bg-background/70 [&>span]:min-w-0 [&>span]:truncate">
        <SelectValue placeholder="Select an agent" />
      </SelectTrigger>
      <SelectContent>
        {specs.map((spec) => (
          <SelectItem key={spec.id} value={String(spec.id)}>
            <div className="flex flex-col items-start">
              <span className="text-sm">{spec.name}</span>
              <span className="text-muted-foreground line-clamp-1 text-[11px]">
                {spec.description}
              </span>
            </div>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function RecentReportsPanel({ activeReportId }: { activeReportId: string | null }) {
  const reportsQuery = useRecentResearchReports(12);

  if (reportsQuery.isLoading) {
    return (
      <div className="space-y-3 px-5 py-5">
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-4/5" />
      </div>
    );
  }

  if (reportsQuery.isError) {
    return (
      <div className="px-5 py-6">
        <div className="rounded-md border border-dashed border-border/70 bg-muted/10 px-4 py-5">
          <p className="text-sm text-foreground">Reports unavailable</p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void reportsQuery.refetch()}
            className="mt-3 h-8 rounded-sm"
          >
            Retry
          </Button>
        </div>
      </div>
    );
  }

  const reports = reportsQuery.data ?? [];
  if (reports.length === 0) {
    return (
      <div className="px-5 py-6">
        <div className="rounded-md border border-dashed border-border/70 bg-muted/10 px-4 py-5">
          <p className="text-sm text-foreground">No saved reports</p>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            Completed runs will appear here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2 px-5 py-4">
      {reports.map((report) => {
        const active = activeReportId === report.id;
        return (
          <Link
            key={report.id}
            href={`/research?reportId=${encodeURIComponent(report.id)}`}
            className={[
              "block rounded-md border px-3 py-3 transition-colors",
              active
                ? "border-primary/35 bg-primary/10"
                : "border-border/60 bg-background/35 hover:border-primary/30 hover:bg-primary/5",
            ].join(" ")}
          >
            <div className="flex items-start gap-2">
              <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
              <div className="min-w-0 flex-1">
                <p className="line-clamp-2 text-sm leading-5 font-medium text-foreground">
                  {reportTitle(report)}
                </p>
                <p className="mt-1 font-mono text-[10px] tracking-[0.08em] text-muted-foreground uppercase">
                  {formatReportTime(report.updated_at ?? report.generated_at)}
                </p>
              </div>
            </div>
            {report.executive_summary ? (
              <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">
                {report.executive_summary}
              </p>
            ) : null}
          </Link>
        );
      })}
    </div>
  );
}

function PersistedReportOutput({ reportId }: { reportId: string }) {
  const reportQuery = useResearchReport(reportId);

  if (reportQuery.isLoading) {
    return (
      <div className="mx-auto max-w-4xl px-8 py-8">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="mt-4 h-10 w-2/3" />
        <Skeleton className="mt-8 h-5 w-full" />
        <Skeleton className="mt-3 h-5 w-11/12" />
        <Skeleton className="mt-3 h-5 w-4/5" />
      </div>
    );
  }

  if (reportQuery.isError || !reportQuery.data) {
    return <div className="px-8 py-7 text-sm text-destructive">Saved report unavailable.</div>;
  }

  const payload = reportQuery.data;
  const title = payload.topic ?? payload.company ?? "Saved report";
  const markdown = payload.markdown;

  return (
    <article className="mx-auto max-w-4xl px-8 py-8">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary" className="rounded-sm">
          <Save className="mr-1.5 h-3 w-3" />
          Saved report
        </Badge>
        <span className="font-mono text-[10px] tracking-[0.12em] text-muted-foreground uppercase">
          {formatReportTime(payload.generated_at)}
        </span>
      </div>
      <h1 className="mt-4 max-w-3xl font-serif text-4xl leading-tight text-foreground">
        {title}
      </h1>
      {markdown ? (
        <MessageResponse className="mt-8 text-[15px] leading-7 text-foreground/90">
          {markdown}
        </MessageResponse>
      ) : (
        <div className="mt-8 space-y-6">
          <p className="text-base leading-7 text-foreground/90">
            {payload.report.executive_summary}
          </p>
          {payload.report.sections.map((section) => (
            <section key={section.name} className="border-t border-border/70 pt-5">
              <h2 className="font-serif text-2xl text-foreground">{section.name}</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {section.summary}
              </p>
            </section>
          ))}
        </div>
      )}
    </article>
  );
}

function OrchestratorOutput({ reportId }: { reportId: string | null }) {
  const { tokens, toolCalls } = useResearchMainStream();
  const { runState, error } = useResearchRunState();

  if (reportId && runState !== "streaming") {
    return <PersistedReportOutput reportId={reportId} />;
  }

  if (runState === "idle") {
    return (
      <div className="flex h-full items-center justify-center px-10">
        <div className="max-w-xl text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full border border-border/70 bg-card/70 shadow-[0_0_40px_rgba(232,89,12,0.08)]">
            <Sparkles className="h-6 w-6 text-primary" />
          </div>
          <p className="font-serif text-3xl text-foreground">Ready for a research run</p>
          <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-muted-foreground">
            Choose a question with a real scope: market, sources, tradeoffs, and an opinionated
            synthesis.
          </p>
          <div className="mt-7 grid grid-cols-4 gap-2">
            {CAPABILITY_BADGES.map((item) => (
              <div
                key={item.label}
                className="flex min-h-20 flex-col items-center justify-center gap-2 rounded-md border border-border/70 bg-muted/20 px-3"
              >
                <item.icon className="h-4 w-4 text-primary" />
                <span className="text-[10px] font-medium tracking-[0.14em] text-muted-foreground uppercase">
                  {item.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (runState === "error") {
    return (
      <div className="mx-auto max-w-4xl px-8 py-8">
        <div className="rounded-md border border-destructive/35 bg-destructive/10 px-4 py-4 text-sm text-destructive">
          <p className="font-medium">Run failed</p>
          <p className="mt-1 text-xs">{error ?? "Unknown error"}</p>
        </div>
        {tokens ? (
          <MessageResponse className="mt-7 text-sm leading-7 text-foreground/90">
            {tokens}
          </MessageResponse>
        ) : null}
      </div>
    );
  }

  if (!tokens) {
    return (
      <div className="flex h-full items-center justify-center px-10">
        <div className="max-w-md text-center">
          <Loader2 className="mx-auto h-6 w-6 animate-spin text-primary" />
          <Shimmer className="mt-4 text-sm" duration={1.6}>
            Orchestrator is planning the run
          </Shimmer>
        </div>
      </div>
    );
  }

  const words = tokens.trim().split(/\s+/).filter(Boolean).length;

  return (
    <div className="mx-auto max-w-5xl px-8 py-7">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-border/60 pb-4">
        <div className="flex items-center gap-2">
          <Badge
            variant={runState === "streaming" ? "default" : "secondary"}
            className="rounded-sm"
          >
            {runState === "streaming" ? (
              <Clock3 className="mr-1.5 h-3 w-3" />
            ) : (
              <CheckCircle2 className="mr-1.5 h-3 w-3" />
            )}
            {runState === "streaming" ? "Streaming" : "Complete"}
          </Badge>
          <span className="font-mono text-[10px] tracking-[0.12em] text-muted-foreground uppercase">
            {words} words
          </span>
        </div>
        {runState === "streaming" ? (
          <Shimmer className="text-xs" duration={1.4}>
            Writing synthesis
          </Shimmer>
        ) : (
          <span className="text-xs text-muted-foreground">Unsaved draft</span>
        )}
      </div>

      {toolCalls.length > 0 ? (
        <section className="mb-6">
          <div className="mb-2 flex items-center gap-2 text-[10px] font-medium tracking-[0.16em] text-muted-foreground uppercase">
            <Bot className="h-3 w-3" />
            Orchestrator Tools
          </div>
          {toolCalls.map((call) => (
            <ResearchToolCall key={call.callId} call={call} />
          ))}
        </section>
      ) : null}

      <MessageResponse
        className="text-[15px] leading-7 text-foreground/90"
        isAnimating={runState === "streaming"}
      >
        {tokens}
      </MessageResponse>
    </div>
  );
}

export function ResearchClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const [topic, setTopic] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);

  const agentsQuery = useResearchAgents();
  const agents = useMemo<ResearchAgentSpec[]>(() => agentsQuery.data ?? [], [agentsQuery.data]);

  const defaultAgentId = useMemo(() => {
    const preferred = agents.find((agent) => agent.slug === "general-research") ?? agents[0];
    return preferred?.id ?? null;
  }, [agents]);

  const agentId = selectedAgentId ?? defaultAgentId;

  const { runState } = useResearchRunState();
  const reportId = useResearchReportId();
  const routeReportId = searchParams.get("reportId");
  const activeReportId = routeReportId ?? (runState === "done" ? reportId : null);
  const { startRun, cancel } = useResearchActions();
  const isStreaming = runState === "streaming";

  const activeSpec = useMemo(
    () => agents.find((agent) => agent.id === agentId) ?? null,
    [agents, agentId],
  );

  useEffect(() => {
    if (!reportId || routeReportId) return;
    void queryClient.invalidateQueries({ queryKey: ["research", "reports"] });
    void queryClient.invalidateQueries({ queryKey: researchReportQueryKey(reportId) });
    router.replace(`/research?reportId=${encodeURIComponent(reportId)}`, { scroll: false });
  }, [queryClient, reportId, routeReportId, router]);

  const handleRun = async () => {
    const trimmedTopic = topic.trim();
    if (!trimmedTopic || agentId === null) return;
    router.replace("/research", { scroll: false });
    await startRun({ topic: trimmedTopic, agent_spec_id: agentId });
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] min-h-0 bg-[radial-gradient(circle_at_45%_0%,rgba(232,89,12,0.08),transparent_32%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent_22%)]">
      <aside className="flex w-[280px] shrink-0 flex-col border-r border-border/60 bg-card/25 2xl:w-[300px]">
        <div className="space-y-4 px-5 pt-5 pb-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] font-medium tracking-[0.18em] text-muted-foreground uppercase">
                Research Desk
              </p>
              <h2 className="mt-1 font-serif text-2xl text-foreground">Deep Research</h2>
            </div>
            <Button size="icon" variant="ghost" asChild className="h-8 w-8 rounded-md">
              <a href="/settings/research-agents" aria-label="Manage agents">
                <SettingsIcon className="h-4 w-4" />
              </a>
            </Button>
          </div>

          <div className="space-y-2">
            <Label htmlFor="agent-picker" className="text-[10px] tracking-[0.12em] uppercase">
              Agent
            </Label>
            <AgentPicker specs={agents} value={agentId} onChange={setSelectedAgentId} />
          </div>

          {activeSpec ? (
            <div className="space-y-3 rounded-md border border-border/70 bg-background/35 p-3">
              <p className="text-sm leading-5 text-muted-foreground">{activeSpec.description}</p>
              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <div className="rounded border border-border/50 bg-muted/20 p-2">
                  <p className="font-medium tracking-[0.12em] text-muted-foreground uppercase">
                    Tools
                  </p>
                  <p className="mt-1 font-mono text-base text-foreground">
                    {activeSpec.tool_allowlist.length}
                  </p>
                </div>
                <div className="rounded border border-border/50 bg-muted/20 p-2">
                  <p className="font-medium tracking-[0.12em] text-muted-foreground uppercase">
                    Agents
                  </p>
                  <p className="mt-1 font-mono text-base text-foreground">
                    {activeSpec.subagents.length}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {activeSpec.tool_allowlist.slice(0, 4).map((tool) => (
                  <Badge key={tool} variant="outline" className="rounded-sm text-[10px]">
                    {tool}
                  </Badge>
                ))}
                {activeSpec.tool_allowlist.length > 4 ? (
                  <Badge variant="secondary" className="rounded-sm text-[10px]">
                    +{activeSpec.tool_allowlist.length - 4}
                  </Badge>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>

        <Separator />

        <div className="px-5 pt-4 pb-2">
          <div className="flex items-center gap-2 text-[10px] font-medium tracking-[0.16em] text-muted-foreground uppercase">
            <ListTodo className="h-3 w-3" />
            Plan
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          <PlanPanel />
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="border-b border-border/60 bg-background/55 px-7 py-4 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="relative min-w-0 flex-1">
              <Input
                placeholder="Research question"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !isStreaming && topic.trim() && agentId !== null) {
                    e.preventDefault();
                    void handleRun();
                  }
                }}
                disabled={isStreaming}
                className="h-12 rounded-md border-border/80 bg-card/80 pr-4 pl-11 text-base shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]"
              />
              <Bot className="absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
            {isStreaming ? (
              <Button
                variant="outline"
                size="lg"
                onClick={() => {
                  cancel();
                  toast.message("Run cancelled");
                }}
                className="h-12 rounded-md px-5"
              >
                <Square className="mr-2 h-4 w-4" />
                Stop
              </Button>
            ) : (
              <Button
                size="lg"
                onClick={handleRun}
                disabled={!topic.trim() || agentId === null}
                className="h-12 rounded-md px-6"
              >
                <Play className="mr-2 h-4 w-4" />
                Run
              </Button>
            )}
            {reportId ? (
              <Button
                variant="outline"
                size="lg"
                asChild
                className="h-12 rounded-md border-primary/30 bg-primary/10 px-4 text-primary hover:bg-primary/15 hover:text-primary"
              >
                <a href={`/research?reportId=${encodeURIComponent(reportId)}`}>
                  <FileText className="mr-2 h-4 w-4" />
                  Saved
                </a>
              </Button>
            ) : null}
          </div>

          <div className="mt-3 hidden gap-2 overflow-x-auto pb-1 2xl:flex">
            {EXAMPLE_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => setTopic(prompt)}
                disabled={isStreaming}
                className="shrink-0 rounded-sm border border-border/70 bg-muted/20 px-3 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:bg-primary/10 hover:text-foreground disabled:opacity-50"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <OrchestratorOutput reportId={activeReportId} />
        </div>
      </main>

      <aside className="flex w-[340px] shrink-0 flex-col border-l border-border/60 bg-card/25 2xl:w-[380px]">
        <Tabs defaultValue="subagents" className="flex h-full flex-col">
          <TabsList className="mx-5 mt-5 grid h-11 grid-cols-3 rounded-md bg-muted/40 p-1">
            <TabsTrigger value="subagents" className="text-xs">
              <Bot className="mr-1.5 h-3 w-3" />
              Sub-agents
            </TabsTrigger>
            <TabsTrigger value="files" className="text-xs">
              <FilesIcon className="mr-1.5 h-3 w-3" />
              Files
            </TabsTrigger>
            <TabsTrigger value="reports" className="text-xs">
              <History className="mr-1.5 h-3 w-3" />
              Reports
            </TabsTrigger>
          </TabsList>
          <TabsContent value="subagents" className="flex-1 overflow-y-auto">
            <SubagentLanes />
          </TabsContent>
          <TabsContent value="files" className="m-0 flex-1 overflow-hidden">
            <FilesPanel />
          </TabsContent>
          <TabsContent value="reports" className="m-0 flex-1 overflow-y-auto">
            <RecentReportsPanel activeReportId={activeReportId} />
          </TabsContent>
        </Tabs>
      </aside>
    </div>
  );
}
