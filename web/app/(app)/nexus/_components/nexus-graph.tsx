"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import Sigma from "sigma";

import {
  DEFAULT_EDGE_COLOR,
  DIMMED_EDGE_COLOR,
  EDGE_TYPE_COLORS,
  PATH_EDGE_COLOR,
  buildNexusGraph,
  sizeForBloom,
} from "@/features/nexus/graph-adapter";
import type { NexusGraph as NexusGraphData } from "@/features/nexus/types";
import { useNexusStore } from "@/lib/stores/nexus-store";

import { ClusterHullLayer } from "./cluster-hull-layer";

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

type Props = {
  data: NexusGraphData;
};

export function NexusGraph({ data }: Props): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);
  const [sigmaInst, setSigmaInst] = useState<Sigma | null>(null);

  // State from Zustand store — select each slice with a selector to avoid
  // unnecessary re-renders.
  const selectedId = useNexusStore((s) => s.selectedId);
  const setSelected = useNexusStore((s) => s.setSelected);
  const setHovered = useNexusStore((s) => s.setHovered);
  const activeEdgeTypes = useNexusStore((s) => s.activeEdgeTypes);
  const activeTopic = useNexusStore((s) => s.activeTopic);
  const focusMode = useNexusStore((s) => s.focusMode);
  const minDegree = useNexusStore((s) => s.minDegree);
  const pathResult = useNexusStore((s) => s.path.result);
  const pathMode = useNexusStore((s) => s.path.mode);
  const pickPathNode = useNexusStore((s) => s.pickPathNode);
  const showClusterHulls = useNexusStore((s) => s.showClusterHulls);
  const pathModeRef = useRef(pathMode);

  useEffect(() => {
    pathModeRef.current = pathMode;
  }, [pathMode]);

  /* ---------------------------------------------------------------- */
  /*  Build the graphology graph from the backend payload              */
  /* ---------------------------------------------------------------- */
  const graph = useMemo(() => buildNexusGraph(data), [data]);

  /* ---------------------------------------------------------------- */
  /*  Mount / unmount Sigma                                            */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    if (!containerRef.current) return;

    const sigma = new Sigma(graph, containerRef.current, {
      renderEdgeLabels: false,
      defaultEdgeColor: DEFAULT_EDGE_COLOR,
      labelColor: { color: "#e5e7eb" },
      labelSize: 11,
      labelWeight: "400",
      labelFont: "DM Sans, sans-serif",
      labelRenderedSizeThreshold: 9,
      hideEdgesOnMove: true,
      hideLabelsOnMove: true,
    });
    sigmaRef.current = sigma;
    setSigmaInst(sigma);

    const handleClickNode = ({ node }: { node: string }) => {
      const id = Number(node);
      if (pathModeRef.current === "picking-start" || pathModeRef.current === "picking-end") {
        pickPathNode(id);
      } else {
        setSelected(id);
      }
    };
    const handleEnterNode = ({ node }: { node: string }) => setHovered(Number(node));
    const handleLeaveNode = () => setHovered(null);
    const handleClickStage = () => setSelected(null);

    sigma.on("clickNode", handleClickNode);
    sigma.on("enterNode", handleEnterNode);
    sigma.on("leaveNode", handleLeaveNode);
    sigma.on("clickStage", handleClickStage);

    return () => {
      sigma.off("clickNode", handleClickNode);
      sigma.off("enterNode", handleEnterNode);
      sigma.off("leaveNode", handleLeaveNode);
      sigma.off("clickStage", handleClickStage);
      sigma.kill();
      sigmaRef.current = null;
      setSigmaInst(null);
    };
  }, [graph, pickPathNode, setHovered, setSelected]);

  /* ---------------------------------------------------------------- */
  /*  Apply selection + path + edge-filter styling                     */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    const g = sigma.getGraph();
    const pathSet = new Set((pathResult ?? []).map(String));
    const selectedNode = selectedId === null ? null : String(selectedId);
    const neighborhood = new Set<string>();
    if (focusMode === "neighborhood" && selectedNode && g.hasNode(selectedNode)) {
      neighborhood.add(selectedNode);
      g.forEachEdge((_edge, _attrs, source, target) => {
        if (source === selectedNode) neighborhood.add(target);
        if (target === selectedNode) neighborhood.add(source);
      });
    }

    g.forEachNode((id, attrs) => {
      const isSelected = selectedNode === id;
      const isInPath = pathSet.has(id);
      const topic = attrs.topic as string | null | undefined;
      const degree = g.degree(id);
      const hiddenByTopic = activeTopic !== null && topic !== activeTopic;
      const hiddenByDegree = degree < minDegree;
      const hiddenByNeighborhood =
        neighborhood.size > 0 && !neighborhood.has(id);
      const hidden =
        !isSelected &&
        !isInPath &&
        (hiddenByTopic || hiddenByDegree || hiddenByNeighborhood);
      g.setNodeAttribute(id, "hidden", hidden);
      g.setNodeAttribute(id, "highlighted", isSelected || isInPath);
      g.setNodeAttribute(id, "forceLabel", isSelected || isInPath);
      const bloom = (attrs.bloom as number | undefined) ?? 1;
      const scale = isSelected ? 1.6 : isInPath ? 1.3 : 1;
      g.setNodeAttribute(id, "size", scale * sizeForBloom(bloom));
    });

    g.forEachEdge((id, attrs, s, t) => {
      if (pathResult && pathResult.length >= 2) {
        const sIdx = pathResult.indexOf(Number(s));
        const tIdx = pathResult.indexOf(Number(t));
        const inPath = sIdx >= 0 && tIdx >= 0 && Math.abs(sIdx - tIdx) === 1;
        g.setEdgeAttribute(id, "hidden", !inPath);
        g.setEdgeAttribute(id, "color", inPath ? PATH_EDGE_COLOR : DIMMED_EDGE_COLOR);
        g.setEdgeAttribute(id, "size", inPath ? 3 : 0.5);
      } else {
        const type = (attrs.relationType as string | undefined) ?? "reference";
        const hidden = activeEdgeTypes.size > 0 && !activeEdgeTypes.has(type);
        g.setEdgeAttribute(id, "hidden", hidden);
        g.setEdgeAttribute(
          id,
          "color",
          hidden ? DIMMED_EDGE_COLOR : EDGE_TYPE_COLORS[type] ?? DEFAULT_EDGE_COLOR,
        );
        g.setEdgeAttribute(id, "size", hidden ? 0.2 : 1);
      }
    });

    sigma.refresh();
  }, [selectedId, pathResult, activeEdgeTypes, activeTopic, focusMode, minDegree]);

  /* ---------------------------------------------------------------- */
  /*  Keep graph focus aligned with sidebar/detail selection           */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    const sigma = sigmaRef.current;
    if (!sigma || selectedId === null) return;

    const g = sigma.getGraph();
    const id = String(selectedId);
    if (!g.hasNode(id)) return;

    const attrs = g.getNodeAttributes(id) as { x?: number; y?: number; hidden?: boolean };
    if (attrs.hidden || attrs.x == null || attrs.y == null) return;

    const camera = sigma.getCamera();
    const state = camera.getState();
    void camera.animate(
      {
        x: attrs.x,
        y: attrs.y,
        ratio: Math.min(state.ratio, 0.35),
      },
      { duration: 420 },
    );
  }, [selectedId]);

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */
  return (
    <div className="relative h-full w-full">
      <div
        ref={containerRef}
        className="h-full w-full bg-[var(--alfred-scene-bg)]"
      />
      <ClusterHullLayer sigma={sigmaInst} graph={graph} enabled={showClusterHulls} />
    </div>
  );
}
