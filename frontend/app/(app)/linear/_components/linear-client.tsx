"use client";

import { useState } from "react";

import { RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { getLinearStatus, listLinearIssues } from "@/lib/api/linear";
import type { LinearIssuesResponse, LinearStatusResponse } from "@/lib/api/types/linear";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { JsonViewer } from "@/components/ui/json-viewer";

export function LinearClient() {
  const [validate, setValidate] = useState(false);
  const [status, setStatus] = useState<LinearStatusResponse | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [includeComments, setIncludeComments] = useState(false);
  const [limit, setLimit] = useState(100);
  const [format, setFormat] = useState<"raw" | "formatted" | "markdown">("raw");

  const [issues, setIssues] = useState<LinearIssuesResponse | null>(null);
  const [issuesLoading, setIssuesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadStatus() {
    setStatusLoading(true);
    setError(null);
    try {
      const res = await getLinearStatus({ validate });
      setStatus(res);
      toast.success("Loaded Linear status.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load status.");
    } finally {
      setStatusLoading(false);
    }
  }

  async function loadIssues() {
    setIssuesLoading(true);
    setError(null);
    try {
      const res = await listLinearIssues({
        start_date: startDate.trim() || null,
        end_date: endDate.trim() || null,
        include_comments: includeComments,
        limit: Math.max(1, Math.min(500, limit)),
        format,
      });
      setIssues(res);
      toast.success("Loaded issues.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load issues.");
    } finally {
      setIssuesLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Linear</h1>
        <p className="text-muted-foreground">Status + issue listing utilities.</p>
      </header>

      {error ? <p className="text-destructive text-sm">{error}</p> : null}

      <Tabs defaultValue="status">
        <TabsList>
          <TabsTrigger value="status">Status</TabsTrigger>
          <TabsTrigger value="issues">Issues</TabsTrigger>
        </TabsList>

        <TabsContent value="status" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between rounded-lg border p-4">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Validate</p>
                  <p className="text-muted-foreground text-xs">
                    Perform a lightweight API call server-side.
                  </p>
                </div>
                <Switch checked={validate} onCheckedChange={setValidate} />
              </div>

              <Button type="button" variant="outline" onClick={() => void loadStatus()} disabled={statusLoading}>
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                {statusLoading ? "Loading…" : "Refresh"}
              </Button>

              {status ? <JsonViewer value={status} title="Status response" /> : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="issues" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>List issues</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="linearStart">Start date (YYYY-MM-DD)</Label>
                  <Input
                    id="linearStart"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    placeholder="e.g. 2025-01-01"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="linearEnd">End date (YYYY-MM-DD)</Label>
                  <Input
                    id="linearEnd"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    placeholder="e.g. 2025-01-31"
                  />
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-3 sm:items-end">
                <div className="space-y-2">
                  <Label htmlFor="linearLimit">Limit</Label>
                  <Input
                    id="linearLimit"
                    inputMode="numeric"
                    value={String(limit)}
                    onChange={(e) => setLimit(Number(e.target.value))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="linearFormat">Format</Label>
                  <select
                    id="linearFormat"
                    className="bg-background h-10 w-full rounded-md border px-3 text-sm"
                    value={format}
                    onChange={(e) => setFormat(e.target.value as typeof format)}
                  >
                    <option value="raw">raw</option>
                    <option value="formatted">formatted</option>
                    <option value="markdown">markdown</option>
                  </select>
                </div>
                <div className="flex items-center justify-between rounded-lg border p-4">
                  <div className="space-y-1">
                    <p className="text-sm font-medium">Include comments</p>
                    <p className="text-muted-foreground text-xs">Adds latency.</p>
                  </div>
                  <Switch checked={includeComments} onCheckedChange={setIncludeComments} />
                </div>
              </div>

              <Button type="button" onClick={() => void loadIssues()} disabled={issuesLoading}>
                {issuesLoading ? "Loading…" : "Fetch"}
              </Button>

              {issues ? <JsonViewer value={issues} title="Issues response" /> : null}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

