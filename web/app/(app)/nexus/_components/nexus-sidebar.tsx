"use client";

import { useMemo, useState } from "react";

import { Input } from "@/components/ui/input";

import { useNexusBridges } from "@/features/nexus/queries";
import type { NexusGraph } from "@/features/nexus/types";
import { useNexusStore } from "@/lib/stores/nexus-store";

import { EdgeTypeLegend } from "./edge-type-legend";

type Props = {
  data: NexusGraph;
};

export function NexusSidebar({ data }: Props): React.ReactElement {
  const [q, setQ] = useState("");
  const setSelected = useNexusStore((s) => s.setSelected);
  const bridges = useNexusBridges(8);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return data.nodes.slice(0, 50);
    return data.nodes
      .filter(
        (n) =>
          n.title.toLowerCase().includes(needle) ||
          (n.topic ?? "").toLowerCase().includes(needle),
      )
      .slice(0, 50);
  }, [q, data.nodes]);

  const edgeTypes = useMemo(() => {
    const set = new Set<string>();
    for (const e of data.edges) set.add(e.type);
    return Array.from(set);
  }, [data.edges]);

  return (
    <aside className="flex h-full w-72 flex-col gap-4 border-r border-border bg-card/90 p-3">
      <div>
        <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
          Search
        </div>
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search zettels…"
          className="mt-1"
        />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
          Zettels ({filtered.length}
          {q ? "" : `/${data.nodes.length}`})
        </div>
        <ul className="mt-1 space-y-0.5">
          {filtered.map((n) => (
            <li key={n.card_id}>
              <button
                type="button"
                onClick={() => setSelected(n.card_id)}
                className="w-full truncate rounded-sm px-2 py-1 text-left text-xs hover:bg-accent"
              >
                {n.title}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <EdgeTypeLegend availableTypes={edgeTypes} />

      <div>
        <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
          Top Bridges
        </div>
        {bridges.data ? (
          <ul className="mt-1 space-y-0.5">
            {bridges.data.map((b) => (
              <li key={b.card_id}>
                <button
                  type="button"
                  onClick={() => setSelected(b.card_id)}
                  className="flex w-full items-center justify-between rounded-sm px-2 py-1 text-left text-xs hover:bg-accent"
                >
                  <span className="truncate">{b.title}</span>
                  <span className="ml-2 font-mono text-[10px] text-muted-foreground">
                    {b.score}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-xs text-muted-foreground">—</div>
        )}
      </div>
    </aside>
  );
}
