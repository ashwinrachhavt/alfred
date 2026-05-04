"use client";

import { useMemo, useState } from "react";
import { Bot, FilesIcon, ListTodo, Play, Settings as SettingsIcon, Square } from "lucide-react";
import { toast } from "sonner";

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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useResearchAgents } from "@/features/research-agents/queries";
import type { ResearchAgentSpec } from "@/lib/api/research-agents";
import {
  useResearchActions,
  useResearchMainStream,
  useResearchRunState,
} from "@/lib/stores/research-store";

import { FilesPanel } from "./files-panel";
import { PlanPanel } from "./plan-panel";
import { SubagentLanes } from "./subagent-lanes";

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
      <SelectTrigger className="h-9">
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

function OrchestratorOutput() {
  const { tokens } = useResearchMainStream();
  const { runState, error } = useResearchRunState();

  if (runState === "idle") {
    return (
      <div className="text-muted-foreground flex h-full items-center justify-center text-center">
        <div className="max-w-md">
          <Bot className="text-muted-foreground/30 mx-auto mb-4 h-10 w-10" />
          <h2 className="text-lg">Ready to research</h2>
          <p className="mt-2 text-sm">
            Pick an agent, enter a topic, and press run. The orchestrator will break it down into
            sub-tasks and delegate each to a sub-agent.
          </p>
        </div>
      </div>
    );
  }

  if (runState === "error") {
    return (
      <div className="text-destructive px-6 py-6 text-sm">
        <p className="font-medium">Run failed</p>
        <p className="mt-1 text-xs">{error ?? "Unknown error"}</p>
      </div>
    );
  }

  if (!tokens) {
    return (
      <div className="text-muted-foreground px-6 py-6 text-sm">Orchestrator is planning...</div>
    );
  }

  return (
    <div className="prose prose-sm dark:prose-invert max-w-none px-6 py-6">
      <pre className="font-sans text-sm leading-relaxed whitespace-pre-wrap">{tokens}</pre>
    </div>
  );
}

export function ResearchClient() {
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
  const { startRun, cancel } = useResearchActions();
  const isStreaming = runState === "streaming";

  const activeSpec = useMemo(
    () => agents.find((agent) => agent.id === agentId) ?? null,
    [agents, agentId],
  );

  const handleRun = async () => {
    const trimmedTopic = topic.trim();
    if (!trimmedTopic || agentId === null) return;
    await startRun({ topic: trimmedTopic, agent_spec_id: agentId });
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] min-h-0">
      <aside className="border-border/60 flex w-72 shrink-0 flex-col border-r">
        <div className="space-y-3 px-4 pt-4 pb-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium tracking-tight">Deep Research</h2>
            <Button size="sm" variant="ghost" asChild className="h-7 px-2">
              <a href="/settings/research-agents" aria-label="Manage agents">
                <SettingsIcon className="h-3.5 w-3.5" />
              </a>
            </Button>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="agent-picker" className="text-xs">
              Agent
            </Label>
            <AgentPicker specs={agents} value={agentId} onChange={setSelectedAgentId} />
          </div>

          {activeSpec ? (
            <div className="space-y-1">
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                {activeSpec.description}
              </p>
              <div className="flex flex-wrap gap-1">
                {activeSpec.tool_allowlist.map((tool) => (
                  <Badge key={tool} variant="outline" className="text-[10px]">
                    {tool}
                  </Badge>
                ))}
                {activeSpec.subagents.map((subagent) => (
                  <Badge key={subagent.name} variant="secondary" className="text-[10px]">
                    {subagent.name}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <Separator />

        <div className="px-4 pt-3 pb-2">
          <div className="text-muted-foreground flex items-center gap-1.5 text-[11px] font-medium tracking-wider uppercase">
            <ListTodo className="h-3 w-3" />
            Plan
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          <PlanPanel />
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="border-border/60 flex items-center gap-3 border-b px-6 py-3">
          <Input
            placeholder="What do you want to research?"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !isStreaming && topic.trim() && agentId !== null) {
                e.preventDefault();
                void handleRun();
              }
            }}
            disabled={isStreaming}
            className="h-9"
          />
          {isStreaming ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                cancel();
                toast.message("Run cancelled");
              }}
            >
              <Square className="mr-1.5 h-3.5 w-3.5" />
              Stop
            </Button>
          ) : (
            <Button size="sm" onClick={handleRun} disabled={!topic.trim() || agentId === null}>
              <Play className="mr-1.5 h-3.5 w-3.5" />
              Run
            </Button>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <OrchestratorOutput />
        </div>
      </main>

      <aside className="border-border/60 flex w-96 shrink-0 flex-col border-l">
        <Tabs defaultValue="subagents" className="flex h-full flex-col">
          <TabsList className="mx-4 mt-4 grid grid-cols-2">
            <TabsTrigger value="subagents" className="text-xs">
              <Bot className="mr-1.5 h-3 w-3" />
              Sub-agents
            </TabsTrigger>
            <TabsTrigger value="files" className="text-xs">
              <FilesIcon className="mr-1.5 h-3 w-3" />
              Files
            </TabsTrigger>
          </TabsList>
          <TabsContent value="subagents" className="flex-1 overflow-y-auto">
            <SubagentLanes />
          </TabsContent>
          <TabsContent value="files" className="m-0 flex-1 overflow-hidden">
            <FilesPanel />
          </TabsContent>
        </Tabs>
      </aside>
    </div>
  );
}
