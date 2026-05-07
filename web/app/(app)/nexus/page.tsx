"use client";

import dynamic from "next/dynamic";

import { useNexusGraph } from "@/features/nexus/queries";

import { NexusDetailsPanel } from "./_components/nexus-details-panel";
import { NexusSidebar } from "./_components/nexus-sidebar";
import { NexusToolbar } from "./_components/nexus-toolbar";

// Sigma.js uses WebGL — skip SSR.
const NexusGraph = dynamic(
  () => import("./_components/nexus-graph").then((m) => m.NexusGraph),
  { ssr: false },
);

export default function NexusPage() {
  const { data, isLoading, error, refetch } = useNexusGraph();

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-background p-6">
        <p className="text-sm text-muted-foreground">
          Nexus graph unavailable. Neo4j may not be synced yet.
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          className="rounded-sm border border-border px-3 py-1.5 text-xs hover:bg-accent"
        >
          Retry
        </button>
        <p className="text-[10px] text-muted-foreground">
          First-time setup: open the page, then click &quot;Rebuild Graph&quot; in the toolbar.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-background">
      <NexusToolbar />
      <div className="flex min-h-0 flex-1">
        {data && <NexusSidebar data={data} />}
        <main className="relative min-w-0 flex-1">
          {isLoading || !data ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Loading graph…
            </div>
          ) : data.nodes.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              No zettels synced yet. Click &quot;Rebuild Graph&quot; above.
            </div>
          ) : (
            <NexusGraph data={data} />
          )}
        </main>
        {data && <NexusDetailsPanel data={data} />}
      </div>
    </div>
  );
}
