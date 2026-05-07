"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import Graph from "graphology";
import louvain from "graphology-communities-louvain";
import forceAtlas2 from "graphology-layout-forceatlas2";
import Sigma from "sigma";

import type { NexusGraph as NexusGraphData } from "@/features/nexus/types";
import { useNexusStore } from "@/lib/stores/nexus-store";

import { ClusterHullLayer } from "./cluster-hull-layer";

/* ------------------------------------------------------------------ */
/*  Visual constants                                                   */
/* ------------------------------------------------------------------ */

const EDGE_TYPE_COLORS: Record<string, string> = {
  reference: "#6b7280",
  extends: "#c47a5a",
  contradicts: "#e8590c",
  supports: "#7a9e7e",
  elaborates: "#8b7ec8",
};

const DEFAULT_EDGE_COLOR = "#4b5563";
const DIMMED_EDGE_COLOR = "#1f2937";
const PATH_EDGE_COLOR = "#e8590c";

// Warm nebula palette (kept in sync with apps/alfred/services/clustering_service.py)
const CLUSTER_PALETTE = [
  "#c47a5a", "#7a9e7e", "#8b7ec8", "#c2956b", "#6b9eb8",
  "#b87a8f", "#9bb86b", "#c4855a", "#6b7eb8", "#b8a06b",
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function sizeForBloom(bloom: number): number {
  // Bloom 1..6 → 5.5 .. 13 px
  return 4 + Math.max(1, Math.min(bloom, 6)) * 1.5;
}

function colorForCluster(cluster: number | null | undefined): string {
  if (cluster == null) return "#9ca3af";
  return CLUSTER_PALETTE[cluster % CLUSTER_PALETTE.length];
}

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
  const pathResult = useNexusStore((s) => s.path.result);
  const pathMode = useNexusStore((s) => s.path.mode);
  const pickPathNode = useNexusStore((s) => s.pickPathNode);
  const showClusterHulls = useNexusStore((s) => s.showClusterHulls);

  /* ---------------------------------------------------------------- */
  /*  Build the graphology graph from the backend payload              */
  /* ---------------------------------------------------------------- */
  const graph = useMemo(() => {
    const g = new Graph({ type: "undirected", multi: false });

    for (const node of data.nodes) {
      g.addNode(String(node.card_id), {
        label: node.title,
        size: sizeForBloom(node.bloom_level),
        x: Math.random(),
        y: Math.random(),
        color: "#9ca3af", // temporary; louvain recolors
        bloom: node.bloom_level,
        topic: node.topic,
        tags: node.tags,
        cluster_id: node.cluster_id,
      });
    }

    for (const edge of data.edges) {
      const s = String(edge.source);
      const t = String(edge.target);
      if (!g.hasNode(s) || !g.hasNode(t)) continue;
      // Simple dedupe: one undirected edge per (source,target). Losing
      // type distinction is fine at this zoom level.
      if (!g.hasEdge(s, t)) {
        g.addEdgeWithKey(`${s}->${t}:${edge.type}`, s, t, {
          type: edge.type,
          color: EDGE_TYPE_COLORS[edge.type] ?? DEFAULT_EDGE_COLOR,
          size: 1,
        });
      }
    }

    // Louvain community detection (trivial graphs can fail; fall back gracefully)
    if (g.order > 1 && g.size > 0) {
      try {
        louvain.assign(g, { nodeCommunityAttribute: "community" });
        g.forEachNode((id, attrs) => {
          const c = attrs.community as number | undefined;
          g.setNodeAttribute(id, "color", colorForCluster(c));
        });
      } catch {
        /* keep default color */
      }
    }

    // Seed a force-directed layout
    if (g.order > 0) {
      try {
        forceAtlas2.assign(g, {
          iterations: 100,
          settings: forceAtlas2.inferSettings(g),
        });
      } catch {
        /* layout can fail on degenerate graphs — ignore */
      }
    }

    return g;
  }, [data]);

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
    });
    sigmaRef.current = sigma;
    setSigmaInst(sigma);

    const handleClickNode = ({ node }: { node: string }) => {
      const id = Number(node);
      if (pathMode === "picking-start" || pathMode === "picking-end") {
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
    // pathMode is captured by closure; include in deps so handler sees
    // current mode without stale refs.
  }, [graph, pathMode, pickPathNode, setHovered, setSelected]);

  /* ---------------------------------------------------------------- */
  /*  Apply selection + path + edge-filter styling                     */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    const g = sigma.getGraph();
    const pathSet = new Set((pathResult ?? []).map(String));

    g.forEachNode((id, attrs) => {
      const isSelected = selectedId !== null && String(selectedId) === id;
      const isInPath = pathSet.has(id);
      g.setNodeAttribute(id, "highlighted", isSelected || isInPath);
      const bloom = (attrs.bloom as number | undefined) ?? 1;
      const scale = isSelected ? 1.6 : isInPath ? 1.3 : 1;
      g.setNodeAttribute(id, "size", scale * sizeForBloom(bloom));
    });

    g.forEachEdge((id, attrs, s, t) => {
      if (pathResult && pathResult.length >= 2) {
        const sIdx = pathResult.indexOf(Number(s));
        const tIdx = pathResult.indexOf(Number(t));
        const inPath = sIdx >= 0 && tIdx >= 0 && Math.abs(sIdx - tIdx) === 1;
        g.setEdgeAttribute(id, "color", inPath ? PATH_EDGE_COLOR : DIMMED_EDGE_COLOR);
        g.setEdgeAttribute(id, "size", inPath ? 3 : 0.5);
      } else {
        const type = (attrs.type as string | undefined) ?? "reference";
        const hidden = activeEdgeTypes.size > 0 && !activeEdgeTypes.has(type);
        g.setEdgeAttribute(
          id,
          "color",
          hidden ? DIMMED_EDGE_COLOR : EDGE_TYPE_COLORS[type] ?? DEFAULT_EDGE_COLOR,
        );
        g.setEdgeAttribute(id, "size", hidden ? 0.2 : 1);
      }
    });

    sigma.refresh();
  }, [selectedId, pathResult, activeEdgeTypes]);

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */
  return (
    <div className="relative h-full w-full">
      <div
        ref={containerRef}
        className="h-full w-full bg-[var(--alfred-scene-bg,#0f0e0d)]"
      />
      <ClusterHullLayer sigma={sigmaInst} graph={graph} enabled={showClusterHulls} />
    </div>
  );
}
