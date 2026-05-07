"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";

import { fetchNexusPath, useNexusSync } from "@/features/nexus/queries";
import { useNexusStore } from "@/lib/stores/nexus-store";

export function NexusToolbar(): React.ReactElement {
  const sync = useNexusSync();
  const [syncStatus, setSyncStatus] = useState<string | null>(null);

  const pathState = useNexusStore((s) => s.path);
  const startPath = useNexusStore((s) => s.startPathPick);
  const resetPath = useNexusStore((s) => s.resetPath);
  const setPathResult = useNexusStore((s) => s.setPathResult);
  const showHulls = useNexusStore((s) => s.showClusterHulls);
  const toggleHulls = useNexusStore((s) => s.toggleClusterHulls);

  const runPath = async () => {
    if (pathState.fromId == null || pathState.toId == null) return;
    const result = await fetchNexusPath(pathState.fromId, pathState.toId);
    setPathResult(result ? result.card_ids : null);
  };

  const doSync = () => {
    sync.mutate(undefined, {
      onSuccess: (r) =>
        setSyncStatus(`Synced: ${r.nodes_synced} nodes, ${r.edges_synced} edges`),
      onError: (e) => setSyncStatus(`Sync failed: ${(e as Error).message}`),
    });
  };

  return (
    <div className="flex items-center gap-2 border-b border-border bg-card/80 px-3 py-2 backdrop-blur">
      <Button variant="outline" size="sm" onClick={doSync} disabled={sync.isPending}>
        {sync.isPending ? "Syncing…" : "Rebuild Graph"}
      </Button>
      <Button variant="outline" size="sm" onClick={toggleHulls}>
        {showHulls ? "Hide Clusters" : "Show Clusters"}
      </Button>

      {pathState.mode === "idle" && (
        <Button variant="outline" size="sm" onClick={startPath}>
          Find Path
        </Button>
      )}
      {pathState.mode === "picking-start" && (
        <span className="text-xs text-muted-foreground">Click source zettel…</span>
      )}
      {pathState.mode === "picking-end" && (
        <span className="text-xs text-muted-foreground">Click target zettel…</span>
      )}
      {pathState.mode === "showing" &&
        pathState.fromId != null &&
        pathState.toId != null &&
        !pathState.result && (
          <Button variant="default" size="sm" onClick={runPath}>
            Trace {pathState.fromId} → {pathState.toId}
          </Button>
        )}
      {pathState.mode === "showing" && pathState.result && (
        <>
          <span className="text-xs text-muted-foreground">
            {pathState.result.length}-hop path
          </span>
          <Button variant="ghost" size="sm" onClick={resetPath}>
            Clear
          </Button>
        </>
      )}

      <div className="ml-auto font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
        {syncStatus}
      </div>
    </div>
  );
}
