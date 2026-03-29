import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

// --- Types ---

export type WhiteboardRevision = {
  id: number;
  whiteboard_id: number;
  revision_no: number;
  scene_json: Record<string, unknown>;
  ai_context: Record<string, unknown> | null;
  applied_prompt: string | null;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type Whiteboard = {
  id: number;
  title: string;
  description: string | null;
  created_by: string | null;
  org_id: string | null;
  template_id: string | null;
  is_archived: boolean;
  created_at: string | null;
  updated_at: string | null;
  latest_revision: WhiteboardRevision | null;
};

// --- Query keys ---

export function canvasListQueryKey() {
  return ["canvases", "list"] as const;
}

export function canvasDetailQueryKey(id: number) {
  return ["canvases", "detail", id] as const;
}

export function canvasRevisionsQueryKey(id: number) {
  return ["canvases", "revisions", id] as const;
}

// --- Hooks ---

export function useCanvasList() {
  return useQuery({
    queryKey: canvasListQueryKey(),
    queryFn: () => apiFetch<Whiteboard[]>(apiRoutes.whiteboards.list),
    staleTime: 10_000,
  });
}

export function useCanvas(id: number | null) {
  return useQuery({
    enabled: id !== null,
    queryKey: id !== null ? canvasDetailQueryKey(id) : ["canvases", "detail", "disabled"],
    queryFn: () => apiFetch<Whiteboard>(apiRoutes.whiteboards.byId(id!)),
    staleTime: 0,
  });
}

export function useCanvasRevisions(id: number | null) {
  return useQuery({
    enabled: id !== null,
    queryKey: id !== null ? canvasRevisionsQueryKey(id) : ["canvases", "revisions", "disabled"],
    queryFn: () => apiFetch<WhiteboardRevision[]>(apiRoutes.whiteboards.revisions(id!)),
    staleTime: 30_000,
  });
}
