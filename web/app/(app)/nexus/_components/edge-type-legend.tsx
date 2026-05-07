"use client";

import { useNexusStore } from "@/lib/stores/nexus-store";

const LEGEND: { type: string; color: string; label: string }[] = [
  { type: "reference", color: "#6b7280", label: "Reference" },
  { type: "extends", color: "#c47a5a", label: "Extends" },
  { type: "contradicts", color: "#e8590c", label: "Contradicts" },
  { type: "supports", color: "#7a9e7e", label: "Supports" },
  { type: "elaborates", color: "#8b7ec8", label: "Elaborates" },
];

type Props = {
  availableTypes: string[];
};

export function EdgeTypeLegend({ availableTypes }: Props): React.ReactElement | null {
  const active = useNexusStore((s) => s.activeEdgeTypes);
  const toggle = useNexusStore((s) => s.toggleEdgeType);
  const shown = LEGEND.filter((l) => availableTypes.includes(l.type));
  if (shown.length === 0) return null;
  return (
    <div className="space-y-1">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
        Edge Types
      </div>
      {shown.map((l) => {
        const isDim = active.size > 0 && !active.has(l.type);
        return (
          <button
            key={l.type}
            type="button"
            onClick={() => toggle(l.type)}
            className={`flex w-full items-center gap-2 rounded-sm px-1 py-0.5 text-left text-xs hover:bg-accent ${
              isDim ? "opacity-40" : ""
            }`}
          >
            <span className="h-0.5 w-4" style={{ backgroundColor: l.color }} />
            <span>{l.label}</span>
          </button>
        );
      })}
    </div>
  );
}
