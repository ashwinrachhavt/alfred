"use client";

import Link from "next/link";

import type { NexusGraph } from "@/features/nexus/types";
import { useNexusStore } from "@/lib/stores/nexus-store";

type Props = {
  data: NexusGraph;
};

export function NexusDetailsPanel({ data }: Props): React.ReactElement | null {
  const selectedId = useNexusStore((s) => s.selectedId);
  const setSelected = useNexusStore((s) => s.setSelected);
  if (selectedId == null) return null;

  const node = data.nodes.find((n) => n.card_id === selectedId);
  if (!node) return null;

  const nodeById = new Map(data.nodes.map((n) => [n.card_id, n]));
  const outgoing = data.edges.filter((e) => e.source === selectedId);
  const incoming = data.edges.filter((e) => e.target === selectedId);

  return (
    <aside className="flex h-full w-80 flex-col gap-4 border-l border-white/10 bg-[var(--alfred-scene-bg)] p-4 text-white shadow-2xl">
      <div>
        <div className="text-[10px] uppercase tracking-wide text-white/35">
          Selected Idea
        </div>
        <h2 className="mt-1 font-serif text-lg leading-tight text-white">{node.title}</h2>
      </div>

      <div className="flex flex-wrap gap-1">
        {node.topic && (
          <span className="rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-primary">
            {node.topic}
          </span>
        )}
        {node.tags.map((t) => (
          <span
            key={t}
            className="rounded-full border border-white/10 bg-white/[0.06] px-2 py-0.5 text-[10px] text-white/55"
          >
            {t}
          </span>
        ))}
      </div>

      <div className="text-xs text-white/45">
        Bloom level{" "}
        <span className="font-mono text-white/80">{node.bloom_level}/6</span>
      </div>

      <div>
        <div className="text-[10px] uppercase tracking-wide text-white/35">
          Extends To ({outgoing.length})
        </div>
        <ul className="mt-1 space-y-1 text-xs">
          {outgoing.slice(0, 10).map((e, i) => (
            <li key={`out-${i}`}>
              <button
                type="button"
                onClick={() => setSelected(e.target)}
                className="w-full rounded-md px-2 py-1.5 text-left text-white/65 hover:bg-white/[0.06] hover:text-white"
              >
                <span className="block truncate">
                  {nodeById.get(e.target)?.title ?? `#${e.target}`}
                </span>
                <span className="text-[10px] uppercase tracking-wide text-white/30">
                  {e.type}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div>
        <div className="text-[10px] uppercase tracking-wide text-white/35">
          Referenced By ({incoming.length})
        </div>
        <ul className="mt-1 space-y-1 text-xs">
          {incoming.slice(0, 10).map((e, i) => (
            <li key={`in-${i}`}>
              <button
                type="button"
                onClick={() => setSelected(e.source)}
                className="w-full rounded-md px-2 py-1.5 text-left text-white/65 hover:bg-white/[0.06] hover:text-white"
              >
                <span className="block truncate">
                  {nodeById.get(e.source)?.title ?? `#${e.source}`}
                </span>
                <span className="text-[10px] uppercase tracking-wide text-white/30">
                  {e.type}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <Link
        href={`/knowledge?card=${node.card_id}`}
        className="mt-auto rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-center text-xs text-white/70 hover:bg-white/10 hover:text-white"
      >
        Open in Knowledge
      </Link>
    </aside>
  );
}
