"use client";

import { useEffect, useMemo, useState } from "react";

import { useQueryClient } from "@tanstack/react-query";
import { Calendar, Mail } from "lucide-react";
import { toast } from "sonner";

import type { GmailMessagePreview } from "@/lib/api/types/google";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useFetchCalendarEvents,
  useFetchGmailMessage,
  useFetchGmailMessages,
  useGoogleAuthUrl,
  useGoogleRevoke,
} from "@/features/google/mutations";
import { useGmailProfile, useGoogleStatus } from "@/features/google/queries";
import { googleQueryKeys } from "@/features/google/query-keys";
import { formatMaybeDate } from "@/lib/utils/format";

function openOAuthPopup(url: string) {
  const width = 640;
  const height = 760;
  const left = window.screenX + (window.outerWidth - width) / 2;
  const top = window.screenY + (window.outerHeight - height) / 2;

  return window.open(
    url,
    "Alfred Google OAuth",
    `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`,
  );
}

export function CalendarEmailClient() {
  const queryClient = useQueryClient();
  const statusQuery = useGoogleStatus();
  const profileQuery = useGmailProfile(Boolean(statusQuery.data?.gmail_token_present));
  const authUrlMutation = useGoogleAuthUrl();
  const revokeMutation = useGoogleRevoke();
  const gmailMessagesMutation = useFetchGmailMessages();
  const gmailMessageMutation = useFetchGmailMessage();
  const calendarEventsMutation = useFetchCalendarEvents();

  const [gmailQuery, setGmailQuery] = useState("newer_than:7d");
  const [gmailMaxResults, setGmailMaxResults] = useState(20);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);

  const gmailConnected = Boolean(statusQuery.data?.gmail_token_present);
  const calendarConnected = Boolean(statusQuery.data?.calendar_token_present);
  const configured = Boolean(statusQuery.data?.configured);

  const messageDialogOpen = Boolean(selectedMessageId);

  const selectedMessage = useMemo(() => {
    if (!selectedMessageId) return null;
    return gmailMessageMutation.data?.id === selectedMessageId ? gmailMessageMutation.data : null;
  }, [gmailMessageMutation.data, selectedMessageId]);

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (!event.data || typeof event.data !== "object") return;
      const payload = event.data as { type?: string; ok?: boolean };
      if (payload.type !== "alfred:google_oauth") return;
      void queryClient.invalidateQueries({ queryKey: googleQueryKeys.status });
      void queryClient.invalidateQueries({ queryKey: googleQueryKeys.gmailProfile });
      toast[payload.ok ? "success" : "error"](
        payload.ok ? "Google connected." : "Google connection failed.",
      );
    };

    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [queryClient]);

  const startOAuth = async () => {
    if (!configured) {
      toast.error("Google OAuth is not configured on the server.");
      return;
    }

    try {
      const result = await authUrlMutation.mutateAsync();
      const popup = openOAuthPopup(result.authorization_url);
      if (!popup) {
        window.location.href = result.authorization_url;
        return;
      }

      const startedAt = Date.now();
      const poll = window.setInterval(() => {
        if (popup.closed) {
          window.clearInterval(poll);
          void queryClient.invalidateQueries({ queryKey: googleQueryKeys.status });
          void queryClient.invalidateQueries({ queryKey: googleQueryKeys.gmailProfile });
        }
        if (Date.now() - startedAt > 3 * 60 * 1000) {
          window.clearInterval(poll);
        }
      }, 500);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start Google OAuth.");
    }
  };

  const disconnect = async () => {
    try {
      await revokeMutation.mutateAsync();
      await queryClient.invalidateQueries({ queryKey: googleQueryKeys.status });
      await queryClient.invalidateQueries({ queryKey: googleQueryKeys.gmailProfile });
      toast.success("Disconnected Google.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to disconnect Google.");
    }
  };

  const loadEmails = async () => {
    if (!gmailConnected) {
      toast.error("Connect Gmail first.");
      return;
    }

    try {
      await gmailMessagesMutation.mutateAsync({
        query: gmailQuery.trim(),
        maxResults: Math.max(1, Math.min(25, gmailMaxResults)),
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load emails.");
    }
  };

  const loadUpcomingEvents = async () => {
    if (!calendarConnected) {
      toast.error("Connect Calendar first.");
      return;
    }

    const start = new Date();
    const end = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);

    try {
      await calendarEventsMutation.mutateAsync({
        start: start.toISOString(),
        end: end.toISOString(),
        maxResults: 250,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load calendar events.");
    }
  };

  const openMessage = async (message: GmailMessagePreview) => {
    setSelectedMessageId(message.id);
    try {
      await gmailMessageMutation.mutateAsync({ id: message.id });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load message.");
    }
  };

  const closeMessageDialog = () => {
    setSelectedMessageId(null);
  };

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Calendar & Email</h1>
        <p className="text-muted-foreground">
          Connect a Google account, then fetch Gmail previews and upcoming calendar events on
          demand.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Google connection</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {statusQuery.isFetching && !statusQuery.data ? (
            <div className="space-y-2">
              <Skeleton className="h-4 w-44" />
              <Skeleton className="h-4 w-60" />
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={configured ? "default" : "destructive"}>
                {configured ? "Configured" : "Not configured"}
              </Badge>
              <Badge variant={gmailConnected ? "default" : "secondary"}>
                Gmail: {gmailConnected ? "Connected" : "Not connected"}
              </Badge>
              <Badge variant={calendarConnected ? "default" : "secondary"}>
                Calendar: {calendarConnected ? "Connected" : "Not connected"}
              </Badge>
              {statusQuery.data?.expires_at ? (
                <span className="text-muted-foreground text-xs">
                  token expires: {formatMaybeDate(statusQuery.data.expires_at)}
                </span>
              ) : null}
            </div>
          )}

          {configured ? null : (
            <p className="text-muted-foreground text-sm">
              Set <code className="bg-muted rounded px-1 py-0.5">GOOGLE_CLIENT_ID</code>,{" "}
              <code className="bg-muted rounded px-1 py-0.5">GOOGLE_CLIENT_SECRET</code>, and{" "}
              <code className="bg-muted rounded px-1 py-0.5">GOOGLE_REDIRECT_URI</code> on the
              backend.
            </p>
          )}

          {profileQuery.data?.email_address ? (
            <p className="text-muted-foreground text-sm">
              Connected as <span className="font-medium">{profileQuery.data.email_address}</span>
            </p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => void startOAuth()}
              disabled={!configured || authUrlMutation.isPending}
            >
              {authUrlMutation.isPending ? "Opening…" : "Connect Google"}
            </Button>
            <Button
              variant="outline"
              onClick={() => void disconnect()}
              disabled={revokeMutation.isPending || (!gmailConnected && !calendarConnected)}
            >
              {revokeMutation.isPending ? "Disconnecting…" : "Disconnect"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="size-4" />
              Gmail
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-[1fr_120px_auto] sm:items-end">
              <div className="space-y-2">
                <Label htmlFor="gmailQuery">Query</Label>
                <Input
                  id="gmailQuery"
                  value={gmailQuery}
                  onChange={(e) => setGmailQuery(e.target.value)}
                  placeholder='e.g. newer_than:7d (interview OR "phone screen")'
                  disabled={!gmailConnected}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="gmailMaxResults">Max</Label>
                <Input
                  id="gmailMaxResults"
                  inputMode="numeric"
                  value={String(gmailMaxResults)}
                  onChange={(e) => setGmailMaxResults(Number(e.target.value))}
                  disabled={!gmailConnected}
                />
              </div>
              <Button
                type="button"
                onClick={() => void loadEmails()}
                disabled={!gmailConnected || gmailMessagesMutation.isPending}
              >
                {gmailMessagesMutation.isPending ? "Loading…" : "Fetch"}
              </Button>
            </div>

            <Separator />

            {gmailMessagesMutation.data?.items?.length ? (
              <div className="space-y-3">
                {gmailMessagesMutation.data.items.map((msg) => (
                  <button
                    key={msg.id}
                    type="button"
                    className="hover:bg-muted/30 w-full rounded-lg border p-3 text-left transition-colors"
                    onClick={() => void openMessage(msg)}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">
                          {msg.headers.Subject ?? "Untitled"}
                        </p>
                        <p className="text-muted-foreground mt-1 line-clamp-2 text-xs">
                          {msg.snippet ?? "—"}
                        </p>
                      </div>
                      <div className="text-muted-foreground shrink-0 text-xs">
                        {msg.headers.From ? (
                          <div className="max-w-44 truncate">{msg.headers.From}</div>
                        ) : null}
                        {msg.internal_date ? <div>{formatMaybeDate(msg.internal_date)}</div> : null}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            ) : gmailMessagesMutation.isPending ? (
              <div className="space-y-2">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">
                {gmailConnected
                  ? "Fetch messages to see previews here."
                  : "Connect Google to fetch Gmail previews."}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="size-4" />
              Calendar
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                onClick={() => void loadUpcomingEvents()}
                disabled={!calendarConnected || calendarEventsMutation.isPending}
              >
                {calendarEventsMutation.isPending ? "Loading…" : "Load next 7 days"}
              </Button>
              <span className="text-muted-foreground text-xs">Primary calendar events.</span>
            </div>

            <Separator />

            {Array.isArray(calendarEventsMutation.data?.items) &&
            calendarEventsMutation.data?.items?.length ? (
              <div className="space-y-3">
                {calendarEventsMutation.data.items.slice(0, 25).map((event, idx) => {
                  const e = event as {
                    summary?: string;
                    start?: { dateTime?: string; date?: string };
                  };
                  const startRaw = e.start?.dateTime ?? e.start?.date;
                  const summary = e.summary ?? "Untitled event";
                  return (
                    <div key={`${idx}-${e.summary ?? "event"}`} className="rounded-lg border p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{summary}</p>
                          <p className="text-muted-foreground mt-1 text-xs">
                            {formatMaybeDate(startRaw)}
                          </p>
                        </div>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            const start = startRaw ? new Date(startRaw) : null;
                            const dueAt =
                              start && !Number.isNaN(start.valueOf())
                                ? new Date(start.getTime() - 24 * 60 * 60 * 1000).toISOString()
                                : new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();

                          }}
                        >
                          View
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : calendarEventsMutation.isPending ? (
              <div className="space-y-2">
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">
                {calendarConnected
                  ? "Load events to see them here."
                  : "Connect Google to fetch calendar events."}
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog
        open={messageDialogOpen}
        onOpenChange={(open) => {
          if (!open) closeMessageDialog();
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{selectedMessage?.headers?.Subject ?? "Email"}</DialogTitle>
            <DialogDescription>
              {selectedMessage?.headers?.From ? `From: ${selectedMessage.headers.From}` : null}
            </DialogDescription>
          </DialogHeader>

          {gmailMessageMutation.isPending && !selectedMessage ? (
            <div className="space-y-2">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          ) : selectedMessage ? (
            <div className="space-y-3">
              <div className="text-muted-foreground text-xs">
                {selectedMessage.headers.Date ? (
                  <div>Date: {selectedMessage.headers.Date}</div>
                ) : null}
                {selectedMessage.internal_date ? (
                  <div>Received: {formatMaybeDate(selectedMessage.internal_date)}</div>
                ) : null}
              </div>
              <pre className="bg-muted max-h-[50vh] overflow-auto rounded-lg p-3 text-sm whitespace-pre-wrap">
                {selectedMessage.body ?? selectedMessage.snippet ?? "—"}
              </pre>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">Select a message to view.</p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
