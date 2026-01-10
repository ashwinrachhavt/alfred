"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PenTool, Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { createWhiteboard, listWhiteboards } from "@/lib/api/whiteboards";
import type { WhiteboardWithRevision } from "@/lib/api/types/whiteboards";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { JsonViewer } from "@/components/ui/json-viewer";

function formatError(err: unknown): string {
  return err instanceof Error ? err.message : "Something went wrong.";
}

export function WhiteboardsClient() {
  const [includeArchived, setIncludeArchived] = useState(false);
  const [limit, setLimit] = useState(50);
  const [boards, setBoards] = useState<WhiteboardWithRevision[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await listWhiteboards({
        include_archived: includeArchived,
        limit: Math.max(1, Math.min(200, limit)),
        skip: 0,
      });
      setBoards(res);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  }

  async function create() {
    const title = newTitle.trim();
    if (!title) return;
    try {
      const res = await createWhiteboard({
        title,
        description: newDescription.trim() || null,
      });
      toast.success("Whiteboard created.");
      setBoards((prev) => [res, ...prev]);
      setNewTitle("");
      setNewDescription("");
    } catch (err) {
      toast.error(formatError(err));
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <PenTool className="text-muted-foreground h-5 w-5" aria-hidden="true" />
          <h1 className="text-3xl font-semibold tracking-tight">Whiteboards</h1>
        </div>
        <p className="text-muted-foreground">Create and manage whiteboards with revisions and comments.</p>
      </header>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Create</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="wbNewTitle">Title</Label>
              <Input
                id="wbNewTitle"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="e.g. Weekly planning"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="wbNewDesc">Description</Label>
              <Textarea
                id="wbNewDesc"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                rows={4}
              />
            </div>
            <Button type="button" onClick={() => void create()} disabled={!newTitle.trim()}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Create
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle>Browse</CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" onClick={() => void load()} disabled={loading}>
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2 sm:items-end">
              <div className="space-y-2">
                <Label htmlFor="wbLimit">Limit</Label>
                <Input
                  id="wbLimit"
                  inputMode="numeric"
                  value={String(limit)}
                  onChange={(e) => setLimit(Number(e.target.value))}
                />
              </div>
              <div className="flex items-center justify-between rounded-lg border p-4">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Include archived</p>
                  <p className="text-muted-foreground text-xs">Show archived boards.</p>
                </div>
                <Switch checked={includeArchived} onCheckedChange={setIncludeArchived} />
              </div>
            </div>

            {error ? <p className="text-destructive text-sm">{error}</p> : null}

            {boards.length ? (
              <div className="divide-border divide-y rounded-lg border">
                {boards.map((b) => (
                  <Link key={b.id} href={`/whiteboards/${b.id}`} className="hover:bg-muted/30 block p-4 transition-colors">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{b.title}</p>
                        <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">{b.description || "—"}</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <Badge variant={b.is_archived ? "secondary" : "outline"}>
                            {b.is_archived ? "Archived" : "Active"}
                          </Badge>
                          {typeof b.latest_revision?.revision_no === "number" ? (
                            <Badge variant="outline">rev {b.latest_revision.revision_no}</Badge>
                          ) : null}
                        </div>
                      </div>
                      <Badge variant="secondary" className="shrink-0">
                        {b.id}
                      </Badge>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">{loading ? "Loading…" : "No whiteboards yet."}</p>
            )}

            {boards.length ? <JsonViewer value={boards} title="Raw boards" collapsed /> : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

