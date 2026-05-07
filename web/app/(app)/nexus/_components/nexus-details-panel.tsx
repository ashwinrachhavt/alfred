"use client";

import Link from "next/link";

import type { NexusGraph } from "@/features/nexus/types";
import { useNexusStore } from "@/lib/stores/nexus-store";

type Props = {
  data: NexusGraph;
};

export function NexusDetailsPanel({ data }: Props): React.ReactElement | null {
  const selectedId = useNexusStore((s) => s.selectedId);
  if (selectedId == null) return null;

  const node = data.nodes.find((n) => n.card_id === selectedId);
  if (!node) return null;

  const outgoing = data.edges.filter((e) => e.source === selectedId);
  const incoming = data.edges.filter((e) => e.target === selectedId);

  return (
    <aside className="flex h-full w-80 flex-col gap-3 border-l border-border bg-card/90 p-4">
      <div>
        <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
          Zettel
        </div>
        <h2 className="mt-1 font-serif text-lg leading-tight">{node.title}</h2>
      </div>

      <div className="flex flex-wrap gap-1">
        {node.topic && (
          <span className="rounded-sm border border-border px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
            {node.topic}
          </span>
        )}
        {node.tags.map((t) => (
          <span
            key={t}
            className="rounded-sm bg-accent px-2 py-0.5 text-[10px] text-foreground"
          >
            {t}
          </span>
        ))}
      </div>

      <div className="text-xs text-muted-foreground">
        Bloom level{" "}
        <span className="font-mono text-foreground">{node.bloom_level}/6</span>
      </div>

      <div>
        <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
          Outgoing ({outgoing.length})
        </div>
        <ul className="mt-1 text-xs">
          {outgoing.slice(0, 10).map((e, i) => (
            <li key={`out-${i}`}>
              → #{e.target} ({e.type})
            </li>
          ))}
        </ul>
      </div>

      <div>
        <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
          Incoming ({incoming.length})
        </div>
        <ul className="mt-1 text-xs">
          {incoming.slice(0, 10).map((e, i) => (
            <li key={`in-${i}`}>
              ← #{e.source} ({e.type})
            </li>
          ))}
        </ul>
      </div>

      <Link
        href={`/knowledge?card=${node.card_id}`}
        className="mt-auto rounded-sm border border-border px-3 py-1.5 text-center text-xs hover:bg-accent"
      >
        Open in Knowledge →
      </Link>
    </aside>
  );
}
