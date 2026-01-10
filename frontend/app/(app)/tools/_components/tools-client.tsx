"use client";

import { useMemo, useState } from "react";

import { RefreshCw, Send, Wrench } from "lucide-react";
import { toast } from "sonner";

import { slackSend, storeQuery, toolsStatus } from "@/lib/api/tools";
import type { StoreQueryResponse, ToolsStatusResponse } from "@/lib/api/types/tools";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { JsonViewer } from "@/components/ui/json-viewer";

function safeParseJsonObject(raw: string): Record<string, unknown> | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
    return null;
  } catch {
    return null;
  }
}

export function ToolsClient() {
  const [status, setStatus] = useState<ToolsStatusResponse | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  const [collection, setCollection] = useState("");
  const [filterJson, setFilterJson] = useState("{}");
  const [queryLimit, setQueryLimit] = useState(20);
  const [storeResult, setStoreResult] = useState<StoreQueryResponse | null>(null);
  const [storeLoading, setStoreLoading] = useState(false);

  const [slackChannel, setSlackChannel] = useState("");
  const [slackThreadTs, setSlackThreadTs] = useState("");
  const [slackText, setSlackText] = useState("");
  const [slackConfirmOpen, setSlackConfirmOpen] = useState(false);
  const [slackDryRun, setSlackDryRun] = useState(true);
  const [slackResult, setSlackResult] = useState<Record<string, unknown> | null>(null);
  const [slackLoading, setSlackLoading] = useState(false);

  const storeFilter = useMemo(() => safeParseJsonObject(filterJson) ?? null, [filterJson]);

  async function loadStatus() {
    setStatusLoading(true);
    try {
      const res = await toolsStatus();
      setStatus(res);
      toast.success("Loaded tools status.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load tools status.");
    } finally {
      setStatusLoading(false);
    }
  }

  async function runStoreQuery() {
    const col = collection.trim();
    if (!col) return;
    setStoreLoading(true);
    try {
      const res = await storeQuery({
        collection: col,
        filter: storeFilter,
        limit: Math.max(0, Math.min(100, queryLimit)),
      });
      setStoreResult(res);
      toast.success("Query complete.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Store query failed.");
    } finally {
      setStoreLoading(false);
    }
  }

  async function runSlackSend() {
    setSlackLoading(true);
    setSlackConfirmOpen(false);
    try {
      if (slackDryRun) {
        setSlackResult({
          dry_run: true,
          request: {
            channel: slackChannel.trim(),
            thread_ts: slackThreadTs.trim() || null,
            text: slackText,
          },
        });
        toast.message("Dry run only. Toggle off to actually send.");
        return;
      }

      const res = await slackSend({
        channel: slackChannel.trim(),
        thread_ts: slackThreadTs.trim() || null,
        text: slackText,
      });
      setSlackResult(res);
      toast.success("Sent Slack message.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Slack send failed.");
    } finally {
      setSlackLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <Wrench className="text-muted-foreground h-5 w-5" aria-hidden="true" />
          <h1 className="text-3xl font-semibold tracking-tight">Tools</h1>
        </div>
        <p className="text-muted-foreground">Smoke tests for configured backends.</p>
      </header>

      <Tabs defaultValue="status">
        <TabsList>
          <TabsTrigger value="status">Status</TabsTrigger>
          <TabsTrigger value="store">Store query</TabsTrigger>
          <TabsTrigger value="slack">Slack</TabsTrigger>
        </TabsList>

        <TabsContent value="status" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Tools status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button type="button" variant="outline" onClick={() => void loadStatus()} disabled={statusLoading}>
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                {statusLoading ? "Loading…" : "Refresh"}
              </Button>
              {status ? <JsonViewer value={status} title="Status response" /> : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="store" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Store query</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="storeCollection">Collection</Label>
                  <Input
                    id="storeCollection"
                    value={collection}
                    onChange={(e) => setCollection(e.target.value)}
                    placeholder="e.g. documents"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="storeLimit">Limit</Label>
                  <Input
                    id="storeLimit"
                    inputMode="numeric"
                    value={String(queryLimit)}
                    onChange={(e) => setQueryLimit(Number(e.target.value))}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="storeFilter">Filter (JSON object)</Label>
                <Textarea
                  id="storeFilter"
                  value={filterJson}
                  onChange={(e) => setFilterJson(e.target.value)}
                  rows={6}
                />
                {storeFilter ? null : (
                  <p className="text-muted-foreground text-xs">Invalid JSON filter (must be an object).</p>
                )}
              </div>

              <Button type="button" onClick={() => void runStoreQuery()} disabled={!collection.trim() || storeLoading}>
                {storeLoading ? "Running…" : "Query"}
              </Button>

              {storeResult ? <JsonViewer value={storeResult} title="Query result" /> : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="slack" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Send Slack message</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between rounded-lg border p-4">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Dry run</p>
                  <p className="text-muted-foreground text-xs">
                    Prevents sending. Toggle off to actually send to Slack.
                  </p>
                </div>
                <Switch checked={slackDryRun} onCheckedChange={setSlackDryRun} />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="slackChannel">Channel</Label>
                  <Input
                    id="slackChannel"
                    value={slackChannel}
                    onChange={(e) => setSlackChannel(e.target.value)}
                    placeholder="e.g. #general or C12345"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="slackThread">Thread ts (optional)</Label>
                  <Input
                    id="slackThread"
                    value={slackThreadTs}
                    onChange={(e) => setSlackThreadTs(e.target.value)}
                    placeholder="e.g. 1712345678.000100"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="slackText">Message</Label>
                <Textarea
                  id="slackText"
                  value={slackText}
                  onChange={(e) => setSlackText(e.target.value)}
                  rows={5}
                />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  onClick={() => setSlackConfirmOpen(true)}
                  disabled={!slackChannel.trim() || !slackText.trim() || slackLoading}
                >
                  <Send className="h-4 w-4" aria-hidden="true" />
                  {slackDryRun ? "Dry run" : "Send"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setSlackResult(null)}
                  disabled={slackLoading}
                >
                  Clear result
                </Button>
              </div>

              {slackResult ? <JsonViewer value={slackResult} title="Slack result" collapsed /> : null}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={slackConfirmOpen} onOpenChange={setSlackConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{slackDryRun ? "Run Slack dry run?" : "Send Slack message?"}</DialogTitle>
            <DialogDescription>
              {slackDryRun
                ? "This will not send a message. It only shows the payload you would send."
                : "This will send a real Slack message using server credentials."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 rounded-lg border p-3 text-sm">
            <p>
              <span className="text-muted-foreground">channel:</span> {slackChannel.trim()}
            </p>
            {slackThreadTs.trim() ? (
              <p>
                <span className="text-muted-foreground">thread:</span> {slackThreadTs.trim()}
              </p>
            ) : null}
            <p className="text-muted-foreground">message</p>
            <pre className="whitespace-pre-wrap break-words">{slackText}</pre>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setSlackConfirmOpen(false)}>
              Cancel
            </Button>
            <Button type="button" onClick={() => void runSlackSend()} disabled={slackLoading}>
              {slackLoading ? "Working…" : slackDryRun ? "Continue" : "Send"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

