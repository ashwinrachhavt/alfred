"use client";

import dynamic from "next/dynamic";

import { useNexusGraph } from "@/features/nexus/queries";

import { NexusDetailsPanel } from "./_components/nexus-details-panel";
import { NexusSidebar } from "./_components/nexus-sidebar";
import { NexusToolbar } from "./_components/nexus-toolbar";

// Sigma.js uses WebGL — skip SSR.
const NexusGraph = dynamic(
  () => import("./_components/nexus-graph").then((m) => m.NexusGraph),
  {
    ssr: false,
    loading: () => <NexusLoadingState label="Preparing graph view..." />,
  },
);

function NexusLoadingState({ label = "Loading graph..." }: { label?: string }) {
  return (
    <div className="flex h-full items-center justify-center bg-[var(--alfred-scene-bg)] text-sm text-white/45">
      <span className="mr-3 h-2 w-2 animate-pulse rounded-full bg-primary" />
      {label}
    </div>
  );
}

export default function NexusPage() {
  const { data, isLoading, error, refetch } = useNexusGraph();

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-[var(--alfred-scene-bg)] p-6 text-white">
        <p className="text-sm text-white/55">
          Nexus graph unavailable. Neo4j may not be synced yet.
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          className="rounded-md border border-white/15 bg-white/5 px-3 py-1.5 text-xs text-white/80 hover:bg-white/10"
        >
          Retry
        </button>
        <p className="text-[10px] text-white/35">
          First-time setup: open the page, then click &quot;Rebuild Graph&quot; in the toolbar.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-[var(--alfred-scene-bg)] text-white">
      <NexusToolbar />
      <div className="flex min-h-0 flex-1">
        {data && <NexusSidebar data={data} />}
        <main className="relative min-w-0 flex-1">
          {isLoading || !data ? (
            <NexusLoadingState />
          ) : data.nodes.length === 0 ? (
            <div className="flex h-full items-center justify-center bg-[var(--alfred-scene-bg)] text-sm text-white/45">
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
