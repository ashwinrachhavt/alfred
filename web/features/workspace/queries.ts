import { useQuery } from "@tanstack/react-query";

import { hydrateSession, type HydrateResponse } from "@/lib/api/workspace";

export function workspaceSessionKey(sessionId: number) {
  return ["workspace", "session", sessionId] as const;
}

export function useHydrateSession(sessionId: number | null) {
  return useQuery<HydrateResponse>({
    queryKey: ["workspace", "session", sessionId],
    queryFn: () => hydrateSession(sessionId as number),
    enabled: sessionId !== null && Number.isFinite(sessionId),
    staleTime: 30_000,
  });
}
