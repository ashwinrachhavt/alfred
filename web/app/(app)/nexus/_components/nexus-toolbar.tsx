"use client";

import { useEffect, useState } from "react";

import { Layers3, RefreshCw, Route, ScanSearch, X } from "lucide-react";
import { Button } from "@/components/ui/button";

import { fetchNexusPath, useNexusSync } from "@/features/nexus/queries";
import { useNexusStore } from "@/lib/stores/nexus-store";

const BUTTON_CLASS =
  "border-white/15 bg-white/[0.06] text-white/80 shadow-none hover:bg-white/10 hover:text-white";

export function NexusToolbar(): React.ReactElement {
  const sync = useNexusSync();
  const [syncStatus, setSyncStatus] = useState<string | null>(null);
  const [pathError, setPathError] = useState<string | null>(null);

  const pathState = useNexusStore((s) => s.path);
  const startPath = useNexusStore((s) => s.startPathPick);
  const resetPath = useNexusStore((s) => s.resetPath);
  const setPathResult = useNexusStore((s) => s.setPathResult);
  const showHulls = useNexusStore((s) => s.showClusterHulls);
  const toggleHulls = useNexusStore((s) => s.toggleClusterHulls);
  const selectedId = useNexusStore((s) => s.selectedId);
  const focusMode = useNexusStore((s) => s.focusMode);
  const setFocusMode = useNexusStore((s) => s.setFocusMode);
  const activeTopic = useNexusStore((s) => s.activeTopic);
  const minDegree = useNexusStore((s) => s.minDegree);
  const activeEdgeTypes = useNexusStore((s) => s.activeEdgeTypes);
  const clearGraphFilters = useNexusStore((s) => s.clearGraphFilters);

  const { mode, fromId, toId, result } = pathState;

  useEffect(() => {
    if (mode !== "showing" || fromId == null || toId == null || result !== null) {
      return;
    }

    let cancelled = false;
    fetchNexusPath(fromId, toId)
      .then((path) => {
        if (cancelled) return;
        setPathError(null);
        setPathResult(path?.card_ids ?? []);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setPathError(error instanceof Error ? error.message : "Path search failed");
        setPathResult([]);
      })

    return () => {
      cancelled = true;
    };
  }, [fromId, mode, result, setPathResult, toId]);

  const doSync = () => {
    sync.mutate(undefined, {
      onSuccess: (r) =>
        setSyncStatus(`Synced: ${r.nodes_synced} nodes, ${r.edges_synced} edges`),
      onError: (e) => setSyncStatus(`Sync failed: ${(e as Error).message}`),
    });
  };

  const hasFilters =
    activeTopic !== null ||
    minDegree > 0 ||
    activeEdgeTypes.size > 0 ||
    focusMode !== "all";
  const isPathLoading =
    mode === "showing" && fromId != null && toId != null && result === null && !pathError;

  return (
    <div className="flex items-center gap-2 border-b border-white/10 bg-[var(--alfred-scene-bg)] px-3 py-2 backdrop-blur">
      <Button
        variant="outline"
        size="sm"
        onClick={doSync}
        disabled={sync.isPending}
        className={BUTTON_CLASS}
      >
        <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${sync.isPending ? "animate-spin" : ""}`} />
        {sync.isPending ? "Syncing..." : "Rebuild"}
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={toggleHulls}
        className={BUTTON_CLASS}
      >
        <Layers3 className="mr-1.5 h-3.5 w-3.5" />
        {showHulls ? "Hide Clusters" : "Show Clusters"}
      </Button>

      {mode === "idle" && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setPathError(null);
            startPath();
          }}
          className={BUTTON_CLASS}
        >
          <Route className="mr-1.5 h-3.5 w-3.5" />
          Find Path
        </Button>
      )}
      {mode === "picking-start" && (
        <span className="rounded-full border border-primary/25 bg-primary/10 px-2.5 py-1 text-xs text-primary">
          Click a source idea
        </span>
      )}
      {mode === "picking-end" && (
        <span className="rounded-full border border-primary/25 bg-primary/10 px-2.5 py-1 text-xs text-primary">
          Click a target idea
        </span>
      )}
      {mode === "showing" && (
        <>
          <span className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-white/60">
            {isPathLoading
              ? "Tracing path..."
              : pathError
                ? "Path failed"
                : result && result.length > 0
                  ? `${result.length - 1} links in path`
                  : "No path found"}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setPathError(null);
              resetPath();
            }}
            className="text-white/55 hover:bg-white/10 hover:text-white"
          >
            <X className="mr-1.5 h-3.5 w-3.5" />
            Clear Path
          </Button>
        </>
      )}

      <div className="ml-3 h-4 w-px bg-white/10" />
      <Button
        variant="outline"
        size="sm"
        onClick={() => setFocusMode(focusMode === "neighborhood" ? "all" : "neighborhood")}
        disabled={selectedId == null}
        className={BUTTON_CLASS}
      >
        <ScanSearch className="mr-1.5 h-3.5 w-3.5" />
        {focusMode === "neighborhood" ? "All Ideas" : "Related Ideas"}
      </Button>
      {hasFilters && (
        <Button
          variant="ghost"
          size="sm"
          onClick={clearGraphFilters}
          className="text-white/55 hover:bg-white/10 hover:text-white"
        >
          Clear Filters
        </Button>
      )}

      <div className="ml-auto truncate font-mono text-[10px] uppercase tracking-wide text-white/35">
        {syncStatus || "Nexus exploration"}
      </div>
    </div>
  );
}
