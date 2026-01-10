"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ArrowLeft, MessageSquareText, Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import {
  addWhiteboardComment,
  addWhiteboardRevision,
  getWhiteboard,
  listWhiteboardComments,
  listWhiteboardRevisions,
  updateWhiteboard,
} from "@/lib/api/whiteboards";
import type {
  WhiteboardCommentOut,
  WhiteboardRevisionOut,
  WhiteboardWithRevision,
} from "@/lib/api/types/whiteboards";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { JsonViewer } from "@/components/ui/json-viewer";

function formatError(err: unknown): string {
  return err instanceof Error ? err.message : "Something went wrong.";
}

function safeParseJsonObject(raw: string): Record<string, unknown> | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) return parsed as Record<string, unknown>;
    return null;
  } catch {
    return null;
  }
}

export function WhiteboardClient({ boardId }: { boardId: number }) {
  const [board, setBoard] = useState<WhiteboardWithRevision | null>(null);
  const [revisions, setRevisions] = useState<WhiteboardRevisionOut[]>([]);
  const [comments, setComments] = useState<WhiteboardCommentOut[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [archived, setArchived] = useState(false);

  const [newRevisionJson, setNewRevisionJson] = useState("{}");
  const [newCommentBody, setNewCommentBody] = useState("");
  const [newCommentAuthor, setNewCommentAuthor] = useState("");

  const revisionScene = useMemo(() => safeParseJsonObject(newRevisionJson), [newRevisionJson]);

  async function load() {
    if (!Number.isFinite(boardId)) return;
    setIsLoading(true);
    setError(null);
    try {
      const [b, r, c] = await Promise.all([
        getWhiteboard(boardId),
        listWhiteboardRevisions(boardId),
        listWhiteboardComments(boardId),
      ]);
      setBoard(b);
      setRevisions(r);
      setComments(c);
      setTitle(b.title ?? "");
      setDescription(b.description ?? "");
      setArchived(Boolean(b.is_archived));
    } catch (err) {
      setError(formatError(err));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [boardId]);

  async function saveBoard() {
    if (!board) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await updateWhiteboard(boardId, {
        title: title.trim() || null,
        description: description.trim() || null,
        is_archived: archived,
      });
      setBoard(res);
      toast.success("Saved.");
    } catch (err) {
      toast.error(formatError(err));
    } finally {
      setIsLoading(false);
    }
  }

  async function addRevision() {
    if (!revisionScene) {
      toast.error("Revision JSON must be an object.");
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const res = await addWhiteboardRevision(boardId, { scene_json: revisionScene });
      setRevisions((prev) => [res, ...prev]);
      toast.success("Revision added.");
    } catch (err) {
      toast.error(formatError(err));
    } finally {
      setIsLoading(false);
    }
  }

  async function addComment() {
    const body = newCommentBody.trim();
    if (!body) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await addWhiteboardComment(boardId, {
        body,
        author: newCommentAuthor.trim() || null,
        element_id: null,
      });
      setComments((prev) => [res, ...prev]);
      setNewCommentBody("");
      toast.success("Comment added.");
    } catch (err) {
      toast.error(formatError(err));
    } finally {
      setIsLoading(false);
    }
  }

  if (!Number.isFinite(boardId)) {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Whiteboard</h1>
        <p className="text-muted-foreground text-sm">Invalid board id.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button asChild variant="ghost" size="sm">
            <Link href="/whiteboards">
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Back
            </Link>
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => void load()} disabled={isLoading}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </Button>
        </div>

        <div className="space-y-1">
          <h1 className="text-3xl font-semibold tracking-tight">
            {board?.title ?? (isLoading ? "Loading…" : "Whiteboard")}
          </h1>
          {board ? (
            <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
              <Badge variant="secondary">id: {board.id}</Badge>
              <Badge variant="outline">archived: {String(board.is_archived)}</Badge>
            </div>
          ) : null}
        </div>
      </header>

      {error ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Error</CardTitle>
          </CardHeader>
          <CardContent className="text-destructive text-sm">{error}</CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Update board</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="wbTitle">Title</Label>
              <Input id="wbTitle" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="wbDesc">Description</Label>
              <Textarea id="wbDesc" value={description} onChange={(e) => setDescription(e.target.value)} rows={4} />
            </div>
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">Archived</p>
                <p className="text-muted-foreground text-xs">Hide from default lists.</p>
              </div>
              <Switch checked={archived} onCheckedChange={setArchived} />
            </div>
            <Button type="button" onClick={() => void saveBoard()} disabled={!board || isLoading}>
              Save
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Add revision</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="wbRevision">Scene JSON</Label>
              <Textarea
                id="wbRevision"
                value={newRevisionJson}
                onChange={(e) => setNewRevisionJson(e.target.value)}
                rows={8}
              />
              {revisionScene ? null : (
                <p className="text-muted-foreground text-xs">Invalid JSON (must be an object).</p>
              )}
            </div>
            <Button type="button" onClick={() => void addRevision()} disabled={isLoading}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Add revision
            </Button>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle className="text-base">Revisions</CardTitle>
            <Badge variant="outline">{revisions.length}</Badge>
          </CardHeader>
          <CardContent className="space-y-3">
            {revisions.length ? (
              <div className="space-y-2">
                {revisions.slice(0, 20).map((rev) => (
                  <div key={rev.id} className="rounded-lg border p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-medium">Revision {rev.revision_no}</p>
                      <Badge variant="secondary">id: {rev.id}</Badge>
                    </div>
                    {rev.created_at ? (
                      <p className="text-muted-foreground mt-1 text-xs">
                        {new Date(rev.created_at).toLocaleString()}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">No revisions yet.</p>
            )}
            {revisions.length ? <JsonViewer value={revisions} title="Raw revisions" collapsed /> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle className="flex items-center gap-2 text-base">
              <MessageSquareText className="h-4 w-4" aria-hidden="true" />
              Comments
            </CardTitle>
            <Badge variant="outline">{comments.length}</Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="wbAuthor">Author (optional)</Label>
              <Input id="wbAuthor" value={newCommentAuthor} onChange={(e) => setNewCommentAuthor(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="wbComment">Comment</Label>
              <Textarea id="wbComment" value={newCommentBody} onChange={(e) => setNewCommentBody(e.target.value)} rows={4} />
            </div>
            <Button type="button" onClick={() => void addComment()} disabled={!newCommentBody.trim() || isLoading}>
              Add comment
            </Button>

            <Separator />

            {comments.length ? (
              <div className="space-y-2">
                {comments.slice(0, 20).map((c) => (
                  <div key={c.id} className="rounded-lg border p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-medium">{c.author ?? "Anonymous"}</p>
                      <Badge variant="secondary">id: {c.id}</Badge>
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-sm">{c.body}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">No comments yet.</p>
            )}

            {comments.length ? <JsonViewer value={comments} title="Raw comments" collapsed /> : null}
          </CardContent>
        </Card>
      </div>

      {board ? <JsonViewer value={board} title="Raw board" collapsed /> : null}
    </div>
  );
}

