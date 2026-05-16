"use client";

import { useMemo, useState } from "react";

import { GitBranch, Network, Search } from "lucide-react";
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
  const selectedId = useNexusStore((s) => s.selectedId);
  const activeTopic = useNexusStore((s) => s.activeTopic);
  const setActiveTopic = useNexusStore((s) => s.setActiveTopic);
  const minDegree = useNexusStore((s) => s.minDegree);
  const setMinDegree = useNexusStore((s) => s.setMinDegree);
  const focusMode = useNexusStore((s) => s.focusMode);
  const setFocusMode = useNexusStore((s) => s.setFocusMode);
  const bridges = useNexusBridges(8);

  const degreeById = useMemo(() => {
    const map = new Map<number, number>();
    for (const node of data.nodes) map.set(node.card_id, 0);
    for (const edge of data.edges) {
      map.set(edge.source, (map.get(edge.source) ?? 0) + 1);
      map.set(edge.target, (map.get(edge.target) ?? 0) + 1);
    }
    return map;
  }, [data.edges, data.nodes]);

  const topicStats = useMemo(() => {
    const counts = new Map<string, number>();
    for (const node of data.nodes) {
      if (!node.topic) continue;
      counts.set(node.topic, (counts.get(node.topic) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 8);
  }, [data.nodes]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return data.nodes
      .filter((n) => {
        const degree = degreeById.get(n.card_id) ?? 0;
        const matchesQuery =
          !needle ||
          n.title.toLowerCase().includes(needle) ||
          (n.topic ?? "").toLowerCase().includes(needle) ||
          n.tags.some((tag) => tag.toLowerCase().includes(needle));
        const matchesTopic = !activeTopic || n.topic === activeTopic;
        const matchesDegree = degree >= minDegree;
        return matchesQuery && matchesTopic && matchesDegree;
      })
      .sort(
        (a, b) =>
          (degreeById.get(b.card_id) ?? 0) - (degreeById.get(a.card_id) ?? 0) ||
          a.title.localeCompare(b.title),
      )
      .slice(0, 80);
  }, [activeTopic, degreeById, minDegree, q, data.nodes]);

  const edgeTypes = useMemo(() => {
    const set = new Set<string>();
    for (const e of data.edges) set.add(e.type);
    return Array.from(set);
  }, [data.edges]);

  return (
    <aside className="flex h-full w-80 flex-col gap-4 border-r border-white/10 bg-[var(--alfred-scene-bg)] p-3 text-white shadow-2xl">
      <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-wide text-white/35">
          <Search className="h-3 w-3" />
          Search Ideas
        </div>
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search title, topic, tag..."
          className="mt-2 border-white/10 bg-black/30 text-white placeholder:text-white/25"
        />
      </div>

      <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-wide text-white/35">
            <Network className="h-3 w-3" />
            Smart Filters
          </div>
          {(activeTopic || minDegree > 0) && (
            <button
              type="button"
              onClick={() => {
                setActiveTopic(null);
                setMinDegree(0);
              }}
              className="text-[10px] text-white/35 hover:text-white/70"
            >
              Reset
            </button>
          )}
        </div>

        <div className="flex flex-wrap gap-1.5">
          {topicStats.map(([topic, count]) => {
            const active = activeTopic === topic;
            return (
              <button
                key={topic}
                type="button"
                onClick={() => setActiveTopic(active ? null : topic)}
                className={`rounded-full border px-2 py-1 text-[11px] transition ${
                  active
                    ? "border-primary/50 bg-primary/20 text-primary"
                    : "border-white/10 bg-black/25 text-white/55 hover:bg-white/10 hover:text-white/80"
                }`}
              >
                {topic} <span className="text-white/35">{count}</span>
              </button>
            );
          })}
        </div>

        <div className="mt-3 flex items-center justify-between gap-2">
          <span className="text-[11px] text-white/35">Minimum links</span>
          <div className="flex rounded-full border border-white/10 bg-black/25 p-0.5">
            {[0, 2, 5, 10].map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setMinDegree(value)}
                className={`rounded-full px-2 py-0.5 text-[11px] ${
                  minDegree === value
                    ? "bg-white/15 text-white"
                    : "text-white/40 hover:text-white/75"
                }`}
              >
                {value}
              </button>
            ))}
          </div>
        </div>

        <button
          type="button"
          onClick={() => setFocusMode(focusMode === "neighborhood" ? "all" : "neighborhood")}
          disabled={selectedId == null}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-md border border-white/10 bg-black/25 px-3 py-2 text-xs text-white/60 transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          <GitBranch className="h-3.5 w-3.5" />
          {focusMode === "neighborhood" ? "Show full graph" : "Explore selected neighborhood"}
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-white/35">
          <span>Ideas</span>
          <span>
            {filtered.length}
            {q || activeTopic || minDegree > 0 ? ` of ${data.nodes.length}` : ""}
          </span>
        </div>
        <ul className="mt-2 space-y-1">
          {filtered.map((n) => (
            <li key={n.card_id}>
              <button
                type="button"
                onClick={() => setSelected(n.card_id)}
                className={`w-full rounded-md border px-2.5 py-2 text-left transition ${
                  selectedId === n.card_id
                    ? "border-primary/40 bg-primary/15"
                    : "border-transparent hover:border-white/10 hover:bg-white/[0.06]"
                }`}
              >
                <span className="block truncate text-xs text-white/85">{n.title}</span>
                <span className="mt-1 flex items-center gap-2 text-[10px] text-white/35">
                  {n.topic && <span className="truncate text-primary/75">{n.topic}</span>}
                  <span>{degreeById.get(n.card_id) ?? 0} links</span>
                  {n.tags.length > 0 && (
                    <span className="truncate">{n.tags.slice(0, 2).join(", ")}</span>
                  )}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <EdgeTypeLegend availableTypes={edgeTypes} />

      <div>
        <div className="text-[10px] uppercase tracking-wide text-white/35">
          Top Bridges
        </div>
        {bridges.data ? (
          <ul className="mt-1 space-y-0.5">
            {bridges.data.map((b) => (
              <li key={b.card_id}>
                <button
                  type="button"
                  onClick={() => setSelected(b.card_id)}
                  className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs text-white/70 hover:bg-white/[0.06] hover:text-white"
                >
                  <span className="truncate">{b.title}</span>
                  <span className="ml-2 font-mono text-[10px] text-white/35">
                    {b.score}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-xs text-white/35">-</div>
        )}
      </div>
    </aside>
  );
}
