import { useQuery } from "@tanstack/react-query";

import { ApiError, apiFetch } from "@/lib/api/client";
import type { GmailProfileResponse, GoogleStatusResponse } from "@/lib/api/types/google";

import { googleQueryKeys } from "./query-keys";

export function useGoogleStatus() {
  return useQuery({
    queryKey: googleQueryKeys.status,
    queryFn: () => apiFetch<GoogleStatusResponse>("/api/google/status"),
  });
}

export function useGmailProfile(enabled: boolean) {
  return useQuery({
    queryKey: googleQueryKeys.gmailProfile,
    enabled,
    queryFn: () => apiFetch<GmailProfileResponse>("/api/gmail/profile"),
    retry: (count, err) => {
      // Treat 404 as "not connected" rather than retrying noisily.
      if (err instanceof ApiError && err.status === 404) return false;
      return count < 1;
    },
  });
}
