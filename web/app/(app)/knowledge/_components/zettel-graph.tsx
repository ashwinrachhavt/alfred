"use client";

import { useCallback, useMemo, useState } from "react";
import {
 ReactFlow,
 Background,
 Controls,
 MiniMap,
 type Connection,
 type Node,
 type Edge,
 type NodeProps,
 Handle,
 Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { LinkEditorDialog } from "@/components/zettels/link-editor-dialog";
import { BLOOM_COLORS, type Zettel, type BloomLevel } from "./mock-data";

type Props = {
 zettels: Zettel[];
 selectedId: string | null;
 onSelect: (id: string) => void;
};

function ZettelNode({ data }: NodeProps) {
 const d = data as {
 label: string;
 bloomLevel: BloomLevel;
 tags: string[];
 isSelected: boolean;
 backendId: number | null;
 };
 const color = BLOOM_COLORS[d.bloomLevel];
 const canConnect = d.backendId !== null;

 return (
 <div
 className="group rounded-lg border bg-card px-3 py-2 shadow-sm transition-all"
 style={{
 borderColor: d.isSelected ? "var(--primary)" : "var(--border)",
 minWidth: 120 + d.bloomLevel * 10,
 maxWidth: 180 + d.bloomLevel * 10,
 transform:`scale(${0.85 + d.bloomLevel * 0.05})`,
 }}
 >
 <Handle type="target" position={Position.Top} className="!bg-[var(--alfred-text-tertiary)] !size-1.5" />
 <div className="text-[12px] leading-snug">{d.label}</div>
 <div className="mt-1 flex items-center gap-1.5">
 <span className="size-[5px] rounded-full" style={{ backgroundColor: color }} />
 <span className="text-[9px]" style={{ color }}>{d.bloomLevel}/6</span>
 {d.tags[0] && (
 <span className="ml-auto text-[8px] uppercase text-[var(--alfred-text-tertiary)]">{d.tags[0]}</span>
 )}
 </div>
 {/* Source handle enabled only when the node maps to a numeric DB id
  (mock-data ids like "z1" yield backendId=null -> not connectable). */}
 <Handle
 type="source"
 position={Position.Right}
 id="link-source"
 isConnectable={canConnect}
 className="!size-2 !bg-[var(--primary)] opacity-0 transition-opacity group-hover:opacity-100"
 />
 <Handle type="source" position={Position.Bottom} className="!bg-[var(--alfred-text-tertiary)] !size-1.5" />
 </div>
 );
}

const nodeTypes = { zettel: ZettelNode };

function parseBackendId(rawId: string): number | null {
 const n = Number(rawId);
 return Number.isFinite(n) && Number.isInteger(n) ? n : null;
}

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
 data: {
 label: z.title,
 bloomLevel: z.bloomLevel,
 tags: z.tags,
 isSelected: false,
 backendId: parseBackendId(z.id),
 },
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

 const [pendingConnection, setPendingConnection] = useState<{
 source: number;
 target: number;
 } | null>(null);
 const [connectError, setConnectError] = useState<string | null>(null);

 const backendIdByNodeId = useMemo(() => {
 const map = new Map<string, number>();
 for (const n of nodes) {
 const bid = (n.data as unknown as { backendId: number | null }).backendId;
 if (bid !== null && bid !== undefined) map.set(n.id, bid);
 }
 return map;
 }, [nodes]);

 const handleConnect = useCallback(
 (params: Connection) => {
 if (!params.source || !params.target) {
 setConnectError("Incomplete connection — try again.");
 return;
 }
 if (params.source === params.target) {
 setConnectError("Can't link a zettel to itself.");
 return;
 }
 const source = backendIdByNodeId.get(params.source);
 const target = backendIdByNodeId.get(params.target);
 if (source === undefined || target === undefined) {
 setConnectError("One of these nodes isn't backed by a saved zettel yet.");
 return;
 }
 setConnectError(null);
 setPendingConnection({ source, target });
 },
 [backendIdByNodeId],
 );

 return (
 <div className="h-full w-full" style={{ minHeight: 400 }}>
 <ReactFlow
 nodes={nodes}
 edges={edges}
 nodeTypes={nodeTypes}
 onNodeClick={onNodeClick}
 onConnect={handleConnect}
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
 {pendingConnection && (
 <LinkEditorDialog
 open
 onOpenChange={(open) => { if (!open) setPendingConnection(null); }}
 mode="create"
 fromCardId={pendingConnection.source}
 initialToCardId={pendingConnection.target}
 onSaved={() => setPendingConnection(null)}
 />
 )}
 {connectError && (
 <div
 role="status"
 className="bg-card text-muted-foreground absolute bottom-3 left-1/2 -translate-x-1/2 rounded-md border px-3 py-1.5 text-[11px] shadow-sm"
 onAnimationEnd={() => setConnectError(null)}
 >
 {connectError}
 <button
 type="button"
 className="ml-2 underline-offset-2 hover:underline"
 onClick={() => setConnectError(null)}
 >
 dismiss
 </button>
 </div>
 )}
 </div>
 );
}
