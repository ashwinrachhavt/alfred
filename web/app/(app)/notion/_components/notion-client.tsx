"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";

import type { NotionHistoryPage } from "@/lib/api/types/notion";
import { formatErrorMessage } from "@/lib/utils";
import { toDateInputValue } from "@/lib/utils/date-format";
import { useNotionHistory } from "@/features/notion/queries";
import { NotionNotetaker } from "@/app/(app)/notion/_components/notion-notetaker";
import { NotionConnect } from "@/app/(app)/notion/_components/notion-connect";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

function safeCopy(text: string): void {
  void navigator.clipboard
    .writeText(text)
    .then(() => toast.success("Copied."))
    .catch(() => toast.error("Failed to copy."));
}

function PageRow({ page }: { page: NotionHistoryPage }) {
  const lastEdited = page.last_edited_time ? toDateInputValue(page.last_edited_time) : null;

  return (
    <li className="rounded-lg border p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="truncate font-medium">{page.title || "Untitled"}</p>
          <div className="flex flex-wrap gap-2 pt-1">
            <Badge variant="secondary">page_id: {page.page_id}</Badge>
            {lastEdited ? <Badge variant="outline">edited: {lastEdited}</Badge> : null}
            {page.content ? <Badge variant="outline">content: included</Badge> : null}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button type="button" size="sm" variant="outline" onClick={() => safeCopy(page.page_id)}>
            Copy id
          </Button>
        </div>
      </div>
    </li>
  );
}

export function NotionClient() {
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [limit, setLimit] = useState<number>(20);
  const [includeContent, setIncludeContent] = useState<boolean>(false);

  const params = useMemo(
    () => ({
      start_date: startDate || null,
      end_date: endDate || null,
      limit,
      include_content: includeContent,
    }),
    [endDate, includeContent, limit, startDate],
  );

  const historyQuery = useNotionHistory(params);
  const pages = historyQuery.data?.pages ?? [];

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Notion</h1>
        <p className="text-muted-foreground text-sm">
          Review pages visible to the configured Notion integration (server-side token).
        </p>
      </header>

      <NotionConnect />

      <NotionNotetaker />

      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 md:grid-cols-4">
            <div className="space-y-2">
              <Label htmlFor="notionStart">Start date</Label>
              <Input
                id="notionStart"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="notionEnd">End date</Label>
              <Input
                id="notionEnd"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="notionLimit">Limit</Label>
              <Input
                id="notionLimit"
                type="number"
                min={1}
                max={200}
                value={String(limit)}
                onChange={(e) => {
                  const next = Number(e.target.value);
                  setLimit(Number.isFinite(next) ? Math.max(1, Math.min(200, next)) : 20);
                }}
              />
            </div>
            <div className="space-y-2">
              <Label>Include content</Label>
              <div className="flex h-10 items-center gap-2 rounded-md border px-3">
                <input
                  id="notionIncludeContent"
                  type="checkbox"
                  checked={includeContent}
                  onChange={(e) => setIncludeContent(e.target.checked)}
                />
                <label htmlFor="notionIncludeContent" className="text-sm">
                  Fetch blocks (slower)
                </label>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{historyQuery.isFetching ? "Refreshing…" : "Ready"}</Badge>
              <Badge variant="outline">results: {historyQuery.data?.count ?? 0}</Badge>
            </div>
            <Button type="button" variant="outline" onClick={() => historyQuery.refetch()}>
              Refresh
            </Button>
          </div>

          {historyQuery.isError ? (
            <Alert variant="destructive">
              <AlertDescription className="text-destructive">
                {formatErrorMessage(historyQuery.error)}
              </AlertDescription>
            </Alert>
          ) : null}

          <Separator />

          {historyQuery.isLoading ? (
            <p className="text-muted-foreground text-sm">Loading…</p>
          ) : pages.length ? (
            <ul className="space-y-3">
              {pages.map((p) => (
                <PageRow key={p.page_id} page={p} />
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground text-sm">
              No pages found. If this looks wrong, ensure `NOTION_TOKEN` is configured on the
              backend and that pages/databases are shared with the integration.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
