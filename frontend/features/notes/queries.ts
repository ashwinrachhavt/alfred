import { useQuery } from "@tanstack/react-query";

import { getNote, getNoteTree, listWorkspaces } from "@/lib/api/notes";

export function workspacesQueryKey(userId: number | null) {
  return ["notes", "workspaces", userId] as const;
}

export function noteTreeQueryKey(workspaceId: string) {
  return ["notes", "tree", workspaceId] as const;
}

export function noteDetailsQueryKey(noteId: string) {
  return ["notes", "details", noteId] as const;
}

export function useWorkspaces(params: { userId?: number | null } = {}) {
  const userId = params.userId ?? null;
  return useQuery({
    queryKey: workspacesQueryKey(userId),
    queryFn: () => listWorkspaces({ userId }),
    staleTime: 30_000,
  });
}

export function useNoteTree(workspaceId: string | null) {
  return useQuery({
    enabled: Boolean(workspaceId),
    queryKey: workspaceId ? noteTreeQueryKey(workspaceId) : ["notes", "tree", "disabled"],
    queryFn: () => getNoteTree(workspaceId!),
    staleTime: 10_000,
  });
}

export function useNote(noteId: string | null) {
  return useQuery({
    enabled: Boolean(noteId),
    queryKey: noteId ? noteDetailsQueryKey(noteId) : ["notes", "details", "disabled"],
    queryFn: () => getNote(noteId!),
    staleTime: 0,
  });
}

