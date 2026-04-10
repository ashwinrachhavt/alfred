"use client";

import type { ExtendedGraphData } from "@/features/universe/queries";

type Props = { data: ExtendedGraphData };

export function KnowledgeUniverse({ data }: Props) {
  return (
    <div className="flex h-full items-center justify-center">
      <p className="font-mono text-xs text-white/40">
        Universe: {data.nodes.length} cards, {data.edges.length} connections
        {data.meta && `, ${data.meta.cluster_count} clusters`}
      </p>
    </div>
  );
}
