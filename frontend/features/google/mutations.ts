import { useMutation } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import type {
  CalendarEventsResponse,
  GmailMessageResponse,
  GmailMessagesResponse,
  GoogleAuthUrlResponse,
  GoogleRevokeResponse,
} from "@/lib/api/types/google";

export function useGoogleAuthUrl() {
  return useMutation({
    mutationFn: () => apiFetch<GoogleAuthUrlResponse>("/api/google/auth_url"),
  });
}

export function useGoogleRevoke() {
  return useMutation({
    mutationFn: () => apiFetch<GoogleRevokeResponse>("/api/google/revoke", { method: "POST" }),
  });
}

export function useFetchGmailMessages() {
  return useMutation({
    mutationFn: (params: { query: string; maxResults: number }) => {
      const search = new URLSearchParams();
      search.set("query", params.query);
      search.set("max_results", String(params.maxResults));
      return apiFetch<GmailMessagesResponse>(`/api/gmail/messages?${search.toString()}`);
    },
  });
}

export function useFetchGmailMessage() {
  return useMutation({
    mutationFn: (params: { id: string }) =>
      apiFetch<GmailMessageResponse>(`/api/gmail/messages/${encodeURIComponent(params.id)}`),
  });
}

export function useFetchCalendarEvents() {
  return useMutation({
    mutationFn: (params: { start: string; end: string; maxResults: number }) => {
      const search = new URLSearchParams();
      search.set("start_date", params.start);
      search.set("end_date", params.end);
      search.set("max_results", String(params.maxResults));
      return apiFetch<CalendarEventsResponse>(`/api/calendar/events?${search.toString()}`);
    },
  });
}
