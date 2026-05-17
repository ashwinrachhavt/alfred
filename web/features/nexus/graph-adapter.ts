import Graph from "graphology";
import louvain from "graphology-communities-louvain";
import forceAtlas2 from "graphology-layout-forceatlas2";

import type { NexusGraph as NexusGraphData } from "./types";

export const EDGE_TYPE_COLORS: Record<string, string> = {
  reference: "#6b7280",
  extends: "#c47a5a",
  contradicts: "#e8590c",
  supports: "#7a9e7e",
  elaborates: "#8b7ec8",
};

export const DEFAULT_EDGE_COLOR = "#4b5563";
export const DIMMED_EDGE_COLOR = "#1f2937";
export const PATH_EDGE_COLOR = "#e8590c";

const CLUSTER_PALETTE = [
  "#c47a5a", "#7a9e7e", "#8b7ec8", "#c2956b", "#6b9eb8",
  "#b87a8f", "#9bb86b", "#c4855a", "#6b7eb8", "#b8a06b",
];

export function sizeForBloom(bloom: number): number {
  return 4 + Math.max(1, Math.min(bloom, 6)) * 1.5;
}

function colorForCluster(cluster: number | null | undefined): string {
  if (cluster == null) return "#9ca3af";
  return CLUSTER_PALETTE[cluster % CLUSTER_PALETTE.length];
}

function stablePosition(seed: number): { x: number; y: number } {
  const angle = ((seed * 137.508) % 360) * (Math.PI / 180);
  const radius = 0.4 + ((seed * 31) % 100) / 120;
  return {
    x: Math.cos(angle) * radius,
    y: Math.sin(angle) * radius,
  };
}

export function buildNexusGraph(data: NexusGraphData): Graph {
  const graph = new Graph({ type: "undirected", multi: false });

  for (const node of data.nodes) {
    const position = stablePosition(node.card_id);
    graph.addNode(String(node.card_id), {
      label: node.title,
      size: sizeForBloom(node.bloom_level),
      x: position.x,
      y: position.y,
      color: "#9ca3af",
      bloom: node.bloom_level,
      topic: node.topic,
      tags: node.tags,
      cluster_id: node.cluster_id,
    });
  }

  for (const edge of data.edges) {
    const source = String(edge.source);
    const target = String(edge.target);
    if (!graph.hasNode(source) || !graph.hasNode(target)) continue;
    if (!graph.hasEdge(source, target)) {
      graph.addEdgeWithKey(`${source}->${target}:${edge.type}`, source, target, {
        relationType: edge.type,
        color: EDGE_TYPE_COLORS[edge.type] ?? DEFAULT_EDGE_COLOR,
        size: 1,
      });
    }
  }

  if (graph.order > 1 && graph.size > 0) {
    try {
      louvain.assign(graph, { nodeCommunityAttribute: "community" });
      graph.forEachNode((id, attrs) => {
        const community = attrs.community as number | undefined;
        graph.setNodeAttribute(id, "color", colorForCluster(community));
      });
    } catch {
      // Keep the default color if community detection fails on a degenerate graph.
    }
  }

  if (graph.order > 0) {
    try {
      forceAtlas2.assign(graph, {
        iterations: 70,
        settings: forceAtlas2.inferSettings(graph),
      });
    } catch {
      // Layout can fail on degenerate graphs; the initial random positions remain usable.
    }
  }

  return graph;
}
