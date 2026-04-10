"use client";

import { useEffect, useState } from "react";
import { useUniverseStore } from "@/lib/stores/universe-store";
import type { GraphNode } from "@/features/universe/queries";

type Props = {
  nodes: GraphNode[];
  graphRef: React.RefObject<any>;
};

export function CardPreviewOverlay({ nodes, graphRef }: Props) {
  const { selectedNodeIds } = useUniverseStore();
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  const node =
    selectedNodeIds.length === 1
      ? nodes.find((n) => n.id === selectedNodeIds[0])
      : null;

  useEffect(() => {
    if (!node || !graphRef.current) {
      setPos(null);
      return;
    }
    // Find the node's 3D position from the force graph
    const fgNode = graphRef.current
      .graphData()
      .nodes.find((n: any) => n.id === node.id);
    if (!fgNode) {
      setPos(null);
      return;
    }
    const coords = graphRef.current.graph2ScreenCoords(
      fgNode.x,
      fgNode.y,
      fgNode.z,
    );
    if (coords) setPos({ x: coords.x + 20, y: coords.y - 60 });
  }, [node, graphRef, selectedNodeIds]);

  if (!node || !pos) return null;

  return (
    <div
      className="pointer-events-auto absolute z-20 max-w-xs rounded-lg border border-white/10 bg-[#1a1918]/95 p-4 shadow-2xl backdrop-blur-sm"
      style={{ left: `${pos.x}px`, top: `${pos.y}px` }}
    >
      <h3 className="font-serif text-sm font-semibold text-white">
        {node.title}
      </h3>
      {node.topic && (
        <span className="mt-1 inline-block font-mono text-[10px] uppercase tracking-wider text-[#E8590C]">
          {node.topic}
        </span>
      )}
      <div className="mt-2 flex flex-wrap gap-1">
        {node.tags.slice(0, 5).map((tag) => (
          <span
            key={tag}
            className="rounded-sm bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-white/50"
          >
            {tag}
          </span>
        ))}
      </div>
      <div className="mt-2 flex items-center gap-3 font-mono text-[10px] text-white/30">
        <span>{node.degree} connections</span>
        {node.importance > 0 && <span>importance: {node.importance}/10</span>}
        {node.status === "stub" && (
          <span className="text-amber-400">stub</span>
        )}
      </div>
    </div>
  );
}
