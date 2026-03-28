"use client";

import { LayoutGrid, Table2, GitFork, Clock, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export type ViewMode = "cards" | "table" | "graph" | "timeline";

const views: { key: ViewMode; label: string; icon: typeof LayoutGrid }[] = [
  { key: "cards", label: "Cards", icon: LayoutGrid },
  { key: "table", label: "Table", icon: Table2 },
  { key: "graph", label: "Graph", icon: GitFork },
  { key: "timeline", label: "Timeline", icon: Clock },
];

type Props = {
  activeView: ViewMode;
  onViewChange: (view: ViewMode) => void;
  search: string;
  onSearchChange: (value: string) => void;
};

export function ViewToolbar({ activeView, onViewChange, search, onSearchChange }: Props) {
  return (
    <div className="flex items-center gap-2 border-b border-[var(--alfred-ruled-line)] px-4 py-2">
      {views.map((v) => (
        <button
          key={v.key}
          onClick={() => onViewChange(v.key)}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider transition-colors",
            activeView === v.key
              ? "bg-[var(--alfred-accent-muted)] text-primary"
              : "text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
          )}
        >
          <v.icon className="size-3.5" />
          {v.label}
        </button>
      ))}

      <div className="flex-1" />

      <input
        type="text"
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder="Filter zettels..."
        className="w-48 rounded-md border bg-transparent px-3 py-1.5 font-mono text-xs text-foreground outline-none placeholder:text-[var(--alfred-text-tertiary)] focus:border-primary"
      />

      <button className="flex items-center gap-1.5 rounded-md border border-dashed border-primary/40 px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider text-primary/60 transition-colors hover:border-primary hover:text-primary">
        <Sparkles className="size-3.5" />
        3D Explore
      </button>
    </div>
  );
}
