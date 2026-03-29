import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  archiveThinkingSession,
  createThinkingSession,
  decompose,
  forkThinkingSession,
  updateThinkingSession,
} from "@/lib/api/thinking";
import { thinkingSessionQueryKey, thinkingSessionsQueryKey } from "@/features/thinking/queries";

export function useCreateThinkingSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { title?: string | null; topic?: string | null; tags?: string[] }) =>
      createThinkingSession(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: thinkingSessionsQueryKey().slice(0, 2),
      });
    },
  });
}

export function useUpdateThinkingSession(sessionId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      title?: string | null;
      blocks?: unknown[];
      tags?: string[];
      status?: "draft" | "published" | "archived";
      pinned?: boolean;
    }) => updateThinkingSession(sessionId, data),
    onSuccess: (updated) => {
      queryClient.setQueryData(thinkingSessionQueryKey(sessionId), updated);
      queryClient.invalidateQueries({
        queryKey: thinkingSessionsQueryKey().slice(0, 2),
      });
    },
  });
}

export function useArchiveThinkingSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => archiveThinkingSession(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: thinkingSessionsQueryKey().slice(0, 2),
      });
    },
  });
}

export function useForkThinkingSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => forkThinkingSession(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: thinkingSessionsQueryKey().slice(0, 2),
      });
    },
  });
}

export function useDecompose() {
  return useMutation({
    mutationFn: (data: { topic?: string; url?: string; text?: string }) =>
      decompose(data),
  });
}
