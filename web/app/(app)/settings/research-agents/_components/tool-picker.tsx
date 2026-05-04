"use client";

import { memo, useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { ToolCatalogEntry } from "@/lib/api/research-agents";

type ToolPickerProps = {
  catalog: ToolCatalogEntry[];
  selected: string[];
  onToggle: (name: string, checked: boolean) => void;
  label?: string;
  helpText?: string;
};

export const ToolPicker = memo(function ToolPicker({
  catalog,
  selected,
  onToggle,
  label = "Tools",
  helpText,
}: ToolPickerProps) {
  const byCategory = useMemo(() => {
    const groups: Record<string, ToolCatalogEntry[]> = {};
    for (const tool of catalog) {
      (groups[tool.category] ??= []).push(tool);
    }
    return groups;
  }, [catalog]);

  const selectedSet = useMemo(() => new Set(selected), [selected]);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="text-xs">{label}</Label>
        <span className="text-muted-foreground text-[10px]">
          {selected.length} selected
        </span>
      </div>
      {helpText ? (
        <p className="text-muted-foreground text-[11px] leading-relaxed">{helpText}</p>
      ) : null}
      <div className="border-border/60 divide-y rounded-md border">
        {Object.entries(byCategory).map(([category, tools]) => (
          <div key={category} className="px-3 py-2">
            <p className="text-muted-foreground mb-1.5 text-[10px] font-medium uppercase tracking-wider">
              {category}
            </p>
            <ul className="space-y-1.5">
              {tools.map((tool) => {
                const id = `tool-${label.replace(/\s+/g, "-")}-${tool.name}`;
                const isChecked = selectedSet.has(tool.name);
                return (
                  <li key={tool.name} className="flex items-start gap-2">
                    <Checkbox
                      id={id}
                      checked={isChecked}
                      onCheckedChange={(v) => onToggle(tool.name, Boolean(v))}
                      className="mt-0.5"
                    />
                    <label htmlFor={id} className="flex min-w-0 flex-1 cursor-pointer flex-col">
                      <span className="flex items-center gap-1.5">
                        <span className={cn("font-mono text-xs", isChecked && "font-medium")}>
                          {tool.name}
                        </span>
                        {tool.requires_connector ? (
                          <Badge variant="outline" className="text-[9px] font-normal">
                            {tool.requires_connector}
                          </Badge>
                        ) : null}
                      </span>
                      <span className="text-muted-foreground text-[11px] leading-relaxed">
                        {tool.description}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
            {category !== Object.keys(byCategory).at(-1) ? <Separator className="mt-2" /> : null}
          </div>
        ))}
      </div>
    </div>
  );
});
