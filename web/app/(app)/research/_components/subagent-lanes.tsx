"use client";

import { useMemo } from "react";
import { Cpu, Wrench } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useResearchSubagents } from "@/lib/stores/research-store";
import type { DeepToolCall } from "@/lib/stores/research-store";

function ToolCallLine({ call }: { call: DeepToolCall }) {
  return (
    <div className="border-border/60 bg-muted/30 flex items-center gap-2 rounded border px-2 py-1 text-xs">
      <Wrench className="text-muted-foreground h-3 w-3" />
      <span className="font-mono">{call.tool}</span>
      <span
        className={cn(
          "ml-auto text-[10px] uppercase tracking-wider",
          call.status === "done"
            ? "text-emerald-600 dark:text-emerald-400"
            : call.status === "error"
              ? "text-red-600 dark:text-red-400"
              : "text-muted-foreground",
        )}
      >
        {call.status}
      </span>
    </div>
  );
}

export function SubagentLanes() {
  const subagents = useResearchSubagents();
  const lanes = useMemo(
    () =>
      Object.values(subagents).sort((a, b) => b.lastActivityAt - a.lastActivityAt),
    [subagents],
  );

  if (lanes.length === 0) {
    return (
      <div className="text-muted-foreground px-4 py-6 text-xs leading-relaxed">
        No sub-agents running yet. When the orchestrator delegates work, each
        sub-agent will get its own lane here.
      </div>
    );
  }

  return (
    <div className="space-y-4 px-4 py-4">
      {lanes.map((lane) => (
        <section key={lane.name} className="space-y-2">
          <div className="flex items-center gap-2">
            <Cpu className="text-primary h-3.5 w-3.5" />
            <h3 className="text-sm font-medium">{lane.name}</h3>
            <Badge variant="outline" className="ml-auto text-[10px]">
              {lane.toolCalls.length} tool{lane.toolCalls.length === 1 ? "" : "s"}
            </Badge>
          </div>
          {lane.toolCalls.length > 0 ? (
            <div className="space-y-1">
              {lane.toolCalls.map((tc) => (
                <ToolCallLine key={tc.callId} call={tc} />
              ))}
            </div>
          ) : null}
          {lane.tokens ? (
            <p className="text-muted-foreground line-clamp-6 whitespace-pre-wrap text-xs leading-relaxed">
              {lane.tokens}
            </p>
          ) : null}
        </section>
      ))}
    </div>
  );
}
