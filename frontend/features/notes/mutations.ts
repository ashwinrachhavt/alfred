import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createNote,
  createWorkspace,
  updateNote,
  uploadNoteAsset,
} from "@/lib/api/notes";
import type { NoteCreateRequest, NoteUpdateRequest, WorkspaceCreateRequest } from "@/lib/api/types/notes";
import { noteDetailsQueryKey, noteTreeQueryKey, workspacesQueryKey } from "@/features/notes/queries";

export function useCreateWorkspace(params: { userId?: number | null } = {}) {
  const queryClient = useQueryClient();
  const userId = params.userId ?? null;

  return useMutation({
    mutationFn: (payload: WorkspaceCreateRequest) => createWorkspace(payload, { userId }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: workspacesQueryKey(userId) });
    },
  });
}

export function useCreateNote(params: { workspaceId?: string | null } = {}) {
  const queryClient = useQueryClient();
  const workspaceId = params.workspaceId ?? null;

  return useMutation({
    mutationFn: (payload: NoteCreateRequest) => createNote(payload),
    onSuccess: async (created) => {
      queryClient.setQueryData(noteDetailsQueryKey(created.id), created);
      if (workspaceId) {
        await queryClient.invalidateQueries({ queryKey: noteTreeQueryKey(workspaceId) });
      }
    },
  });
}

export function useUpdateNote(noteId: string, params: { workspaceId?: string | null } = {}) {
  const queryClient = useQueryClient();
  const workspaceId = params.workspaceId ?? null;

  return useMutation({
    mutationFn: (payload: NoteUpdateRequest) => updateNote(noteId, payload),
    onSuccess: async (updated) => {
      queryClient.setQueryData(noteDetailsQueryKey(noteId), updated);
      if (workspaceId) {
        await queryClient.invalidateQueries({ queryKey: noteTreeQueryKey(workspaceId) });
      }
    },
  });
}

export function useUploadNoteAsset(noteId: string) {
  return useMutation({
    mutationFn: (file: File) => uploadNoteAsset(noteId, file),
  });
}
