"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Download, Loader2, CheckCircle2, AlertCircle, Archive } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

type ImportState =
  | { phase: "idle" }
  | { phase: "importing"; taskId: string | null }
  | { phase: "completed"; stats: ImportStats }
  | { phase: "error"; message: string };

type ImportStats = {
  created: number;
  updated: number;
  skipped: number;
  errors: { page_id: string; error: string }[];
  documents: { page_id: string; document_id: string }[];
};

type Props = {
  workspaces: { workspace_id: string; workspace_name?: string }[];
  hasEnvToken?: boolean;
};

export function NotionImportSection({ workspaces, hasEnvToken }: Props) {
  const [state, setState] = useState<ImportState>({ phase: "idle" });
  const [limit, setLimit] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>(
    workspaces[0]?.workspace_id ?? "",
  );

  // Can import if there's an env token OR a selected workspace
  const canImport = hasEnvToken || !!selectedWorkspace;
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // Clean up polling on unmount
  useEffect(() => stopPolling, [stopPolling]);

  const pollTaskStatus = useCallback(
    (taskId: string) => {
      pollRef.current = setInterval(async () => {
        try {
          const res = await fetch(`/api/tasks/${taskId}`);
          if (!res.ok) return;
          const data = await res.json();

          if (data.status === "SUCCESS") {
            stopPolling();
            const result = data.result ?? {};
            setState({
              phase: "completed",
              stats: {
                created: result.created ?? 0,
                updated: result.updated ?? 0,
                skipped: result.skipped ?? 0,
                errors: result.errors ?? [],
                documents: result.documents ?? [],
              },
            });
            toast.success(
              `Import complete: ${result.created ?? 0} created, ${result.updated ?? 0} updated`,
            );
          } else if (data.status === "FAILURE") {
            stopPolling();
            setState({ phase: "error", message: data.error ?? "Import failed" });
            toast.error("Notion import failed");
          }
          // PENDING/STARTED — keep polling
        } catch {
          // Network error — keep polling
        }
      }, 2000);
    },
    [stopPolling],
  );

  const handleImport = async () => {
    if (!canImport) {
      toast.error("No workspace or token available");
      return;
    }

    setState({ phase: "importing", taskId: null });

    try {
      const body: Record<string, unknown> = {
        include_archived: includeArchived,
        run_inline: false,
      };
      // Only send workspace_id if using OAuth (not env token)
      if (selectedWorkspace) {
        body.workspace_id = selectedWorkspace;
      }
      if (limit.trim()) {
        const n = parseInt(limit, 10);
        if (n > 0 && n <= 10_000) body.limit = n;
      }

      const res = await fetch("/api/notion/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Import request failed" }));
        throw new Error(err.detail ?? "Import request failed");
      }

      const data = await res.json();

      if (data.status === "completed" && data.result) {
        // Inline mode (Celery not running)
        setState({
          phase: "completed",
          stats: {
            created: data.result.created ?? 0,
            updated: data.result.updated ?? 0,
            skipped: data.result.skipped ?? 0,
            errors: data.result.errors ?? [],
            documents: data.result.documents ?? [],
          },
        });
        toast.success(
          `Import complete: ${data.result.created ?? 0} created, ${data.result.updated ?? 0} updated`,
        );
      } else if (data.task_id) {
        // Async mode — poll for status
        setState({ phase: "importing", taskId: data.task_id });
        pollTaskStatus(data.task_id);
      } else {
        setState({ phase: "error", message: "Unexpected response from import endpoint" });
      }
    } catch (err) {
      setState({
        phase: "error",
        message: err instanceof Error ? err.message : "Import failed",
      });
      toast.error(err instanceof Error ? err.message : "Import failed");
    }
  };

  return (
    <div className="space-y-4 border-t pt-4">
      <Label className="font-mono text-xs uppercase tracking-wider">
        Bulk Import
      </Label>

      {/* Workspace selector */}
      {workspaces.length > 1 && (
        <div className="space-y-1.5">
          <label className="text-xs text-muted-foreground">Workspace</label>
          <select
            value={selectedWorkspace}
            onChange={(e) => setSelectedWorkspace(e.target.value)}
            className="w-full rounded-md border bg-background px-3 py-2 font-mono text-xs"
          >
            {workspaces.map((ws) => (
              <option key={ws.workspace_id} value={ws.workspace_id}>
                {ws.workspace_name ?? ws.workspace_id}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Options */}
      <div className="space-y-3">
        <div className="space-y-1.5">
          <label className="text-xs text-muted-foreground">
            Page limit <span className="text-[var(--alfred-text-tertiary)]">(optional, max 10,000)</span>
          </label>
          <Input
            type="number"
            placeholder="All pages"
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
            min={1}
            max={10000}
            className="font-mono text-xs"
            disabled={state.phase === "importing"}
          />
        </div>

        <div className="flex items-center justify-between">
          <label className="text-xs text-muted-foreground flex items-center gap-1.5">
            <Archive className="size-3" />
            Include archived pages
          </label>
          <Switch
            checked={includeArchived}
            onCheckedChange={setIncludeArchived}
            disabled={state.phase === "importing"}
          />
        </div>
      </div>

      {/* Import button */}
      <Button
        size="sm"
        onClick={() => void handleImport()}
        disabled={state.phase === "importing" || !canImport}
        className="w-full"
      >
        {state.phase === "importing" ? (
          <>
            <Loader2 className="mr-2 size-3.5 animate-spin" />
            Importing...
          </>
        ) : (
          <>
            <Download className="mr-2 size-3.5" />
            Import from Notion
          </>
        )}
      </Button>

      {/* Status */}
      {state.phase === "importing" && state.taskId && (
        <p className="text-xs text-muted-foreground">
          Task: <code className="text-[10px]">{state.taskId.slice(0, 8)}...</code>
          {" "}— polling for completion
        </p>
      )}

      {state.phase === "completed" && (
        <div className="space-y-2 rounded-lg border border-[var(--color-success)]/20 bg-[var(--color-success)]/5 p-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="size-4 text-[var(--color-success)]" />
            <span className="font-mono text-xs font-medium">Import Complete</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className="text-[10px]">
              {state.stats.created} created
            </Badge>
            <Badge variant="outline" className="text-[10px]">
              {state.stats.updated} updated
            </Badge>
            {state.stats.skipped > 0 && (
              <Badge variant="secondary" className="text-[10px]">
                {state.stats.skipped} skipped
              </Badge>
            )}
            {state.stats.errors.length > 0 && (
              <Badge variant="destructive" className="text-[10px]">
                {state.stats.errors.length} errors
              </Badge>
            )}
          </div>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 text-xs"
            onClick={() => setState({ phase: "idle" })}
          >
            Import again
          </Button>
        </div>
      )}

      {state.phase === "error" && (
        <div className="space-y-2 rounded-lg border border-destructive/20 bg-destructive/5 p-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="size-4 text-destructive" />
            <span className="font-mono text-xs font-medium">Import Failed</span>
          </div>
          <p className="text-xs text-muted-foreground">{state.message}</p>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 text-xs"
            onClick={() => setState({ phase: "idle" })}
          >
            Try again
          </Button>
        </div>
      )}
    </div>
  );
}
