import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiPostJson, apiPatchJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import {
  canvasDetailQueryKey,
  canvasListQueryKey,
  type Whiteboard,
  type WhiteboardRevision,
} from "./queries";

// --- Create canvas ---

type CreateCanvasPayload = {
  title: string;
  description?: string | null;
  initial_scene?: Record<string, unknown> | null;
};

export function useCreateCanvas() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateCanvasPayload) =>
      apiPostJson<Whiteboard, CreateCanvasPayload>(apiRoutes.whiteboards.create, payload),
    onSuccess: async (created) => {
      queryClient.setQueryData(canvasDetailQueryKey(created.id), created);
      await queryClient.invalidateQueries({ queryKey: canvasListQueryKey() });
    },
  });
}

// --- Update canvas metadata (title, description, archive) ---

type UpdateCanvasPayload = {
  title?: string;
  description?: string | null;
  is_archived?: boolean;
};

export function useUpdateCanvas(id: number | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: UpdateCanvasPayload) => {
      if (id === null) throw new Error("No canvas selected");
      return apiPatchJson<Whiteboard, UpdateCanvasPayload>(
        apiRoutes.whiteboards.byId(id),
        payload,
      );
    },
    onSuccess: async (updated) => {
      queryClient.setQueryData(canvasDetailQueryKey(updated.id), updated);
      await queryClient.invalidateQueries({ queryKey: canvasListQueryKey() });
    },
  });
}

// --- Save scene (create revision) ---

type SaveScenePayload = {
  scene_json: Record<string, unknown>;
  ai_context?: Record<string, unknown> | null;
  applied_prompt?: string | null;
};

export function useSaveCanvasScene(id: number | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: SaveScenePayload) => {
      if (id === null) throw new Error("No canvas selected");
      return apiPostJson<WhiteboardRevision, SaveScenePayload>(
        apiRoutes.whiteboards.revisions(id),
        payload,
      );
    },
    onSuccess: async () => {
      if (id !== null) {
        await queryClient.invalidateQueries({ queryKey: canvasDetailQueryKey(id) });
      }
    },
  });
}

// --- Delete canvas (archive) ---

export function useDeleteCanvas() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (canvasId: number) =>
      apiPatchJson<Whiteboard, UpdateCanvasPayload>(
        apiRoutes.whiteboards.byId(canvasId),
        { is_archived: true },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: canvasListQueryKey() });
    },
  });
}

// --- Hard delete (if backend supports it, fallback to archive) ---

export function useArchiveCanvas() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (canvasId: number) =>
      apiPatchJson<Whiteboard, UpdateCanvasPayload>(
        apiRoutes.whiteboards.byId(canvasId),
        { is_archived: true },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: canvasListQueryKey() });
    },
  });
}
