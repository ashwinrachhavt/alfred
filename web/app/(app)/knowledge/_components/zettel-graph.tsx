"use client";

import { useCallback, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { BLOOM_COLORS, type Zettel, type BloomLevel } from "./mock-data";

type Props = {
  zettels: Zettel[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

function ZettelNode({ data }: NodeProps) {
  const d = data as { label: string; bloomLevel: BloomLevel; tags: string[]; isSelected: boolean };
  const color = BLOOM_COLORS[d.bloomLevel];

  return (
    <div
      className="rounded-lg border bg-card px-3 py-2 shadow-sm transition-all"
      style={{
        borderColor: d.isSelected ? "var(--primary)" : "var(--border)",
        minWidth: 120 + d.bloomLevel * 10,
        maxWidth: 180 + d.bloomLevel * 10,
        transform: `scale(${0.85 + d.bloomLevel * 0.05})`,
      }}
    >
      <Handle type="target" position={Position.Top} className="!bg-[var(--alfred-text-tertiary)] !size-1.5" />
      <div className="font-serif text-[12px] leading-snug">{d.label}</div>
      <div className="mt-1 flex items-center gap-1.5">
        <span className="size-[5px] rounded-full" style={{ backgroundColor: color }} />
        <span className="font-mono text-[9px]" style={{ color }}>{d.bloomLevel}/6</span>
        {d.tags[0] && (
          <span className="ml-auto font-mono text-[8px] uppercase text-[var(--alfred-text-tertiary)]">{d.tags[0]}</span>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-[var(--alfred-text-tertiary)] !size-1.5" />
    </div>
  );
}

const nodeTypes = { zettel: ZettelNode };

function layoutNodes(zettels: Zettel[]): Node[] {
  // Simple circle layout
  const r = Math.max(200, zettels.length * 35);
  const cx = 400;
  const cy = 400;
  return zettels.map((z, i) => {
    const angle = (i / zettels.length) * 2 * Math.PI - Math.PI / 2;
    return {
      id: z.id,
      type: "zettel",
      position: { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) },
      data: { label: z.title, bloomLevel: z.bloomLevel, tags: z.tags, isSelected: false },
    };
  });
}

function buildEdges(zettels: Zettel[]): Edge[] {
  const ids = new Set(zettels.map((z) => z.id));
  const edges: Edge[] = [];
  const seen = new Set<string>();
  for (const z of zettels) {
    for (const conn of z.connections) {
      if (!ids.has(conn)) continue;
      const key = [z.id, conn].sort().join("-");
      if (seen.has(key)) continue;
      seen.add(key);
      edges.push({
        id: key,
        source: z.id,
        target: conn,
        style: { stroke: "var(--border)", strokeWidth: 1 },
      });
    }
  }
  return edges;
}

export function ZettelGraph({ zettels, selectedId, onSelect }: Props) {
  const nodes = useMemo(() => {
    const base = layoutNodes(zettels);
    return base.map((n) => ({
      ...n,
      data: { ...n.data, isSelected: n.id === selectedId },
    }));
  }, [zettels, selectedId]);

  const edges = useMemo(() => buildEdges(zettels), [zettels]);

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => onSelect(node.id),
    [onSelect],
  );

  return (
    <div className="h-full w-full" style={{ minHeight: 400 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ animated: false }}
      >
        <Background gap={24} size={1} color="var(--alfred-ruled-line)" />
        <Controls showInteractive={false} className="!bg-card !border-[var(--border)] !shadow-sm [&>button]:!bg-card [&>button]:!border-[var(--border)] [&>button]:!text-muted-foreground" />
        <MiniMap
          nodeColor={() => "var(--primary)"}
          maskColor="var(--background)"
          className="!bg-card !border-[var(--border)]"
        />
      </ReactFlow>
    </div>
  );
}
