"use client";

import { Plus, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { SubAgentSpec, ToolCatalogEntry } from "@/lib/api/research-agents";

import { ToolPicker } from "./tool-picker";

type Props = {
  subagents: SubAgentSpec[];
  catalog: ToolCatalogEntry[];
  onChange: (next: SubAgentSpec[]) => void;
};

const EMPTY_SUBAGENT: SubAgentSpec = {
  name: "",
  description: "",
  system_prompt: "",
  tools: [],
  model: null,
};

function SubAgentCard({
  value,
  onChange,
  onDelete,
  catalog,
  defaultOpen = false,
}: {
  value: SubAgentSpec;
  onChange: (next: SubAgentSpec) => void;
  onDelete: () => void;
  catalog: ToolCatalogEntry[];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  const toggleTool = (tool: string, checked: boolean) => {
    const next = checked
      ? [...value.tools, tool]
      : value.tools.filter((t) => t !== tool);
    onChange({ ...value, tools: next });
  };

  return (
    <div className="border-border/60 rounded-md border">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="hover:bg-muted/40 flex w-full items-center gap-2 rounded-t-md px-3 py-2 text-left"
      >
        {open ? (
          <ChevronDown className="text-muted-foreground h-3.5 w-3.5" />
        ) : (
          <ChevronRight className="text-muted-foreground h-3.5 w-3.5" />
        )}
        <span className={cn("font-mono text-xs", !value.name && "text-muted-foreground")}>
          {value.name || "unnamed sub-agent"}
        </span>
        <Badge variant="outline" className="ml-auto text-[10px]">
          {value.tools.length} tools
        </Badge>
      </button>

      {open ? (
        <div className="space-y-3 border-t border-border/60 px-3 py-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor={`sa-name-${value.name}`} className="text-xs">
                Name
              </Label>
              <Input
                id={`sa-name-${value.name}`}
                value={value.name}
                onChange={(e) => onChange({ ...value, name: e.target.value })}
                placeholder="e.g. paper-surveyor"
                className="h-8 font-mono text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`sa-model-${value.name}`} className="text-xs">
                Model override (optional)
              </Label>
              <Input
                id={`sa-model-${value.name}`}
                value={value.model ?? ""}
                onChange={(e) =>
                  onChange({ ...value, model: e.target.value.trim() || null })
                }
                placeholder="openai:gpt-5.2"
                className="h-8 font-mono text-xs"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Description (shown to orchestrator)</Label>
            <Textarea
              value={value.description}
              onChange={(e) => onChange({ ...value, description: e.target.value })}
              placeholder="What this sub-agent does and when to delegate to it."
              rows={2}
              className="text-xs"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">System prompt</Label>
            <Textarea
              value={value.system_prompt}
              onChange={(e) => onChange({ ...value, system_prompt: e.target.value })}
              placeholder="You research..."
              rows={5}
              className="text-xs"
            />
          </div>

          <ToolPicker
            catalog={catalog}
            selected={value.tools}
            onToggle={toggleTool}
            label="Sub-agent tools"
            helpText="Only these tools will be passed to this sub-agent."
          />

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onDelete}
            className="text-destructive hover:text-destructive"
          >
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            Remove sub-agent
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export function SubAgentEditor({ subagents, catalog, onChange }: Props) {
  const patch = (idx: number, next: SubAgentSpec) => {
    const copy = [...subagents];
    copy[idx] = next;
    onChange(copy);
  };

  const remove = (idx: number) => {
    onChange(subagents.filter((_, i) => i !== idx));
  };

  const add = () => {
    onChange([...subagents, { ...EMPTY_SUBAGENT }]);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="text-xs">Sub-agents</Label>
        <Button type="button" variant="outline" size="sm" onClick={add} className="h-7">
          <Plus className="mr-1.5 h-3 w-3" />
          Add sub-agent
        </Button>
      </div>
      <p className="text-muted-foreground text-[11px] leading-relaxed">
        Sub-agents run with isolated context windows. The orchestrator decides when to
        delegate based on each sub-agent&apos;s description.
      </p>

      {subagents.length === 0 ? (
        <p className="border-border/60 text-muted-foreground rounded-md border border-dashed px-3 py-4 text-center text-xs">
          No sub-agents defined. Click Add sub-agent to create one.
        </p>
      ) : (
        <div className="space-y-2">
          {subagents.map((sa, idx) => (
            <SubAgentCard
              key={`${idx}-${sa.name}`}
              value={sa}
              onChange={(next) => patch(idx, next)}
              onDelete={() => remove(idx)}
              catalog={catalog}
              defaultOpen={!sa.name}
            />
          ))}
        </div>
      )}
    </div>
  );
}
