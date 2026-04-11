"use client";

import { useEffect, useState } from "react";
import { type ForceGraphMethods } from "react-force-graph-3d";
import { useUniverseStore } from "@/lib/stores/universe-store";
import type { GraphEdge, GraphNode } from "@/features/universe/queries";

type PositionedGraphNode = GraphNode & { x?: number; y?: number; z?: number };
type GraphRef = React.MutableRefObject<
  ForceGraphMethods<PositionedGraphNode, GraphEdge> | undefined
>;

type Props = {
  nodes: PositionedGraphNode[];
  graphRef: GraphRef;
};

export function CardPreviewOverlay({ nodes, graphRef }: Props) {
  const { selectedNodeIds } = useUniverseStore();
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  const node =
    selectedNodeIds.length === 1
      ? nodes.find((n) => n.id === selectedNodeIds[0])
      : null;

  useEffect(() => {
    let frame = 0;
    if (!node || !graphRef.current) {
      frame = window.requestAnimationFrame(() => setPos(null));
      return () => window.cancelAnimationFrame(frame);
    }
    const positionedNode = nodes.find((n) => n.id === node.id);
    if (
      !positionedNode
      || positionedNode.x === undefined
      || positionedNode.y === undefined
      || positionedNode.z === undefined
    ) {
      frame = window.requestAnimationFrame(() => setPos(null));
      return () => window.cancelAnimationFrame(frame);
    }

    const coords = graphRef.current.graph2ScreenCoords(
      positionedNode.x,
      positionedNode.y,
      positionedNode.z,
    );
    frame = window.requestAnimationFrame(() =>
      setPos(coords ? { x: coords.x + 20, y: coords.y - 60 } : null),
    );
    return () => window.cancelAnimationFrame(frame);
  }, [graphRef, node, nodes]);

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
