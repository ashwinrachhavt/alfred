"use client";

import dynamic from "next/dynamic";
import { useExtendedGraph } from "@/features/universe/queries";

const KnowledgeUniverse = dynamic(
  () => import("./_components/knowledge-universe").then((m) => m.KnowledgeUniverse),
  { ssr: false }
);

export default function UniversePage() {
  const { data, isLoading, error, refetch } = useExtendedGraph();

  // Desktop-only guard
  if (typeof window !== "undefined" && window.innerWidth < 768) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0F0E0D] text-white/60">
        <p className="max-w-xs text-center font-sans text-sm">
          The Knowledge Universe is best experienced on desktop.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-[#0F0E0D]">
        <p className="font-sans text-sm text-white/60">Couldn&apos;t load your universe.</p>
        <button
          onClick={() => refetch()}
          className="rounded-md bg-[#E8590C] px-4 py-2 font-sans text-xs text-white"
        >
          Retry
        </button>
      </div>
    );
  }

  if (isLoading || !data) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0F0E0D]">
        <div className="h-3 w-3 animate-pulse rounded-full bg-[#E8590C]" />
        <span className="ml-3 font-mono text-xs text-white/40">Loading your universe...</span>
      </div>
    );
  }

  // Empty state
  if (data.nodes.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 bg-[#0F0E0D]">
        <p className="font-sans text-sm text-white/60">Your universe is empty.</p>
        <p className="font-sans text-xs text-white/30">
          Start by creating your first knowledge card.
        </p>
        <a
          href="/knowledge"
          className="rounded-md bg-[#E8590C] px-4 py-2 font-sans text-xs text-white"
        >
          Go to Knowledge Hub
        </a>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full bg-[#0F0E0D]">
      <KnowledgeUniverse data={data} />
    </div>
  );
}
