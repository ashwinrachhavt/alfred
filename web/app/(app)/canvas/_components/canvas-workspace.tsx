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
      </ReactFlow>
    </div>
  );
}
