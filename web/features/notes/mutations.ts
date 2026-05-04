import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createNote,
  createWorkspace,
  deleteNote,
  importNoteFilesystem,
  importUploadedNoteFilesystem,
  updateNote,
  uploadNoteAsset,
} from "@/lib/api/notes";
import type {
  NoteFilesystemImportRequest,
  NoteFilesystemUploadImportRequest,
  NoteCreateRequest,
  NoteUpdateRequest,
  WorkspaceCreateRequest,
} from "@/lib/api/types/notes";
import {
  noteDetailsQueryKey,
  noteTreeQueryKey,
  workspacesQueryKey,
} from "@/features/notes/queries";

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
    onSuccess: async (updated, payload) => {
      queryClient.setQueryData(noteDetailsQueryKey(noteId), updated);
      const changesTree =
        "title" in payload ||
        "icon" in payload ||
        "cover_image" in payload ||
        "is_archived" in payload;
      if (workspaceId && changesTree) {
        await queryClient.invalidateQueries({ queryKey: noteTreeQueryKey(workspaceId) });
      }
    },
  });
}

export function useDeleteNote(
  params: { workspaceId?: string | null; onSuccess?: () => void } = {},
) {
  const queryClient = useQueryClient();
  const workspaceId = params.workspaceId ?? null;

  return useMutation({
    mutationFn: (noteId: string) => deleteNote(noteId),
    onSuccess: async () => {
      if (workspaceId) {
        await queryClient.invalidateQueries({ queryKey: noteTreeQueryKey(workspaceId) });
      }
      params.onSuccess?.();
    },
  });
}

export function useImportNoteFilesystem(params: { workspaceId?: string | null } = {}) {
  const queryClient = useQueryClient();
  const workspaceId = params.workspaceId ?? null;

  return useMutation({
    mutationFn: (payload: NoteFilesystemImportRequest) => importNoteFilesystem(payload),
    onSuccess: async () => {
      if (workspaceId) {
        await queryClient.invalidateQueries({ queryKey: noteTreeQueryKey(workspaceId) });
      }
    },
  });
}

export function useImportUploadedNoteFilesystem(params: { workspaceId?: string | null } = {}) {
  const queryClient = useQueryClient();
  const workspaceId = params.workspaceId ?? null;

  return useMutation({
    mutationFn: (payload: NoteFilesystemUploadImportRequest) =>
      importUploadedNoteFilesystem(payload),
    onSuccess: async () => {
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
