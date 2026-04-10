"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ForceGraph3D } from "react-force-graph";
import * as THREE from "three";
import type { ExtendedGraphData, GraphNode } from "@/features/universe/queries";
import { useUniverseStore } from "@/lib/stores/universe-store";

type Props = { data: ExtendedGraphData };

export function KnowledgeUniverse({ data }: Props) {
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  const { selectedNodeIds, selectNode, clearSelection, setHoveredNode } =
    useUniverseStore();

  // Measure container with ResizeObserver
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(([entry]) => {
      setDimensions({
        width: entry.contentRect.width,
        height: entry.contentRect.height,
      });
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // Configure force simulation after mount
  useEffect(() => {
    if (!fgRef.current) return;
    const fg = fgRef.current;
    fg.d3Force("charge")?.strength(-120);
    fg.d3Force("link")?.distance(50);
  }, [data]);

  // Custom node rendering with Three.js
  const nodeThreeObject = useCallback(
    (node: any) => {
      const gn = node as GraphNode & { x?: number; y?: number; z?: number };
      const size = Math.max(2, Math.log2((gn.degree || 0) + 1) * 2.5);
      const isStub = gn.status === "stub";
      const isSelected = selectedNodeIds.includes(gn.id);

      const geometry = new THREE.SphereGeometry(size, 16, 12);
      const material = new THREE.MeshPhongMaterial({
        color: isStub ? 0x555555 : 0xe8590c,
        wireframe: isStub,
        transparent: true,
        opacity: isSelected ? 1.0 : 0.75,
        emissive: isSelected ? 0xe8590c : 0x331100,
        emissiveIntensity: isSelected ? 0.6 : 0.15,
      });
      return new THREE.Mesh(geometry, material);
    },
    [selectedNodeIds],
  );

  // Click handlers
  const handleNodeClick = useCallback(
    (node: any, event: MouseEvent) => {
      if (event.shiftKey) {
        selectNode(node.id);
      } else {
        clearSelection();
        selectNode(node.id);
      }
    },
    [selectNode, clearSelection],
  );

  // Prepare graph data — ForceGraph3D expects "links" not "edges"
  const graphData = useMemo(
    () => ({
      nodes: data.nodes.map((n) => ({ ...n })),
      links: data.edges.map((e) => ({ ...e })),
    }),
    [data],
  );

  return (
    <div ref={containerRef} className="h-full w-full">
      <ForceGraph3D
        ref={fgRef}
        graphData={graphData}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="#0F0E0D"
        nodeThreeObject={nodeThreeObject}
        nodeThreeObjectExtend={false}
        onNodeClick={handleNodeClick}
        onNodeHover={(node: any) => setHoveredNode(node?.id ?? null)}
        nodeLabel={(node: any) =>
          `${node.title} (${node.degree} connections)`
        }
        warmupTicks={100}
        cooldownTime={5000}
        showNavInfo={false}
        enableNavigationControls={true}
      />
    </div>
  );
}
