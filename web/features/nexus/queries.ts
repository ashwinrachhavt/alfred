"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

import type {
  NexusBridge,
  NexusGraph,
  NexusPath,
  NexusSyncResult,
} from "./types";

const NEXUS_KEYS = {
  all: ["nexus"] as const,
  graph: (limit: number) => ["nexus", "graph", limit] as const,
  bridges: (limit: number) => ["nexus", "bridges", limit] as const,
};

export function useNexusGraph(limit = 5000) {
  return useQuery({
    queryKey: NEXUS_KEYS.graph(limit),
    queryFn: () =>
      apiFetch<NexusGraph>(`${apiRoutes.nexus.graph}?limit=${limit}`),
    staleTime: 60_000,
  });
}

export function useNexusBridges(limit = 10) {
  return useQuery({
    queryKey: NEXUS_KEYS.bridges(limit),
    queryFn: () =>
      apiFetch<NexusBridge[]>(`${apiRoutes.nexus.bridges}?limit=${limit}`),
    staleTime: 60_000,
  });
}

export function useNexusSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<NexusSyncResult>(apiRoutes.nexus.sync, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: NEXUS_KEYS.all });
    },
  });
}

/**
 * One-shot path fetch used by the toolbar — not a hook because it's
 * triggered by a button click, not bound to component lifecycle. Returns
 * null on 404 (no path) instead of throwing.
 */
export async function fetchNexusPath(
  from: number,
  to: number,
): Promise<NexusPath | null> {
  try {
    return await apiFetch<NexusPath>(
      `${apiRoutes.nexus.path}?from_id=${from}&to_id=${to}`,
    );
  } catch {
    return null;
  }
}
