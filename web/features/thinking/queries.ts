import { useQuery } from "@tanstack/react-query";

import {
  getThinkingSession,
  listThinkingSessions,
} from "@/lib/api/thinking";

export function thinkingSessionsQueryKey(status?: string, limit?: number) {
  return ["thinking", "sessions", { status, limit }] as const;
}

export function thinkingSessionQueryKey(id: number) {
  return ["thinking", "sessions", id] as const;
}

export function useThinkingSessions(status?: string, limit = 50) {
  return useQuery({
    queryKey: thinkingSessionsQueryKey(status, limit),
    queryFn: () => listThinkingSessions({ status, limit }),
  });
}

export function useThinkingSession(id: number | null) {
  return useQuery({
    enabled: id != null,
    queryKey: id != null ? thinkingSessionQueryKey(id) : ["thinking", "disabled"],
    queryFn: () => getThinkingSession(id!),
  });
}
