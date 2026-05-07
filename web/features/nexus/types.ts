/**
 * Types mirroring the backend Pydantic DTOs at apps/alfred/schemas/nexus.py.
 * Keep in lockstep with the backend; a mismatch surfaces as a runtime JSON
 * parse error at the React Query boundary.
 */

export type NexusNode = {
  card_id: number;
  title: string;
  topic: string | null;
  tags: string[];
  bloom_level: number;
  cluster_id: number | null;
};

export type NexusEdge = {
  source: number;
  target: number;
  type: string;
};

export type NexusGraph = {
  nodes: NexusNode[];
  edges: NexusEdge[];
};

export type NexusPath = {
  card_ids: number[];
};

export type NexusBridge = {
  card_id: number;
  title: string;
  score: number;
};

export type NexusSyncResult = {
  nodes_synced: number;
  edges_synced: number;
};
