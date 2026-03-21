"use client";

import { useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import CanvasEdge from "./canvas-edge";
import ConceptNode from "./canvas-node-concept";
import DocumentNode from "./canvas-node-document";
import ZettelNode from "./canvas-node-zettel";
import { CanvasToolbar } from "./canvas-toolbar";

const nodeTypes = {
  document: DocumentNode,
  concept: ConceptNode,
  zettel: ZettelNode,
};

const edgeTypes = {
  canvas: CanvasEdge,
};

type Props = {
  initialNodes?: Node[];
  initialEdges?: Edge[];
};

export function CanvasWorkspace({ initialNodes = [], initialEdges = [] }: Props) {
  const [nodes, _setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges],
  );

  return (
    <div className="relative h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        defaultEdgeOptions={{ type: "canvas" }}
        fitView
        className="bg-background"
      >
        <Background gap={20} size={1} />
        <Controls showInteractive={false} className="!bg-background !border !shadow-sm" />
        <MiniMap className="!bg-muted !border" />
        <CanvasToolbar />
        {nodes.length === 0 && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <div className="mb-4 flex justify-center">
                <div className="flex size-16 items-center justify-center rounded-full bg-muted/50">
                  <svg className="size-8 text-muted-foreground/50" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                  </svg>
                </div>
              </div>
              <p className="text-muted-foreground/60 text-lg font-medium">Your canvas is empty</p>
              <p className="text-muted-foreground/40 mt-1 text-sm">
                Drag items from your Inbox, or click + to create a note
              </p>
            </div>
          </div>
        )}
      </ReactFlow>
    </div>
  );
}
