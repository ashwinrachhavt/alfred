import { useQuery, queryOptions, keepPreviousData } from "@tanstack/react-query";

import { browseNoteFilesystem, getNote, getNoteTree, listWorkspaces } from "@/lib/api/notes";

export function workspacesQueryKey(userId: number | null) {
  return ["notes", "workspaces", userId] as const;
}

export function noteTreeQueryKey(workspaceId: string) {
  return ["notes", "tree", workspaceId] as const;
}

export function noteDetailsQueryKey(noteId: string) {
  return ["notes", "details", noteId] as const;
}

export function noteFilesystemBrowseQueryKey(path: string | null) {
  return ["notes", "filesystem", "browse", path ?? "__root__"] as const;
}

export function workspacesQueryOptions(params: { userId?: number | null } = {}) {
  const userId = params.userId ?? null;
  return queryOptions({
    queryKey: workspacesQueryKey(userId),
    queryFn: () => listWorkspaces({ userId }),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
}

export function useWorkspaces(params: { userId?: number | null } = {}) {
  return useQuery(workspacesQueryOptions(params));
}

export function useNoteTree(workspaceId: string | null) {
  return useQuery({
    enabled: Boolean(workspaceId),
    queryKey: workspaceId ? noteTreeQueryKey(workspaceId) : ["notes", "tree", "disabled"],
    queryFn: () => getNoteTree(workspaceId!),
    staleTime: 30_000,
  });
}

export function useNote(noteId: string | null) {
  return useQuery({
    enabled: Boolean(noteId),
    queryKey: noteId ? noteDetailsQueryKey(noteId) : ["notes", "details", "disabled"],
    queryFn: () => getNote(noteId!),
    staleTime: 15_000,
  });
}

export function useNoteFilesystemBrowse(path: string | null, enabled: boolean) {
  return useQuery({
    enabled,
    queryKey: noteFilesystemBrowseQueryKey(path),
    queryFn: () => browseNoteFilesystem(path),
    staleTime: 5_000,
    placeholderData: keepPreviousData,
  });
}
