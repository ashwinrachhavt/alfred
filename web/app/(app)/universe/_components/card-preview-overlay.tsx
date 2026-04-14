"use client";

import { useEffect } from "react";
import { X, ExternalLink } from "lucide-react";
import { useUniverseStore } from "@/lib/stores/universe-store";
import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { useQuery } from "@tanstack/react-query";
import type { GraphNode } from "@/features/universe/queries";

type ApiCard = {
  id: number;
  title: string;
  content: string | null;
  summary: string | null;
  tags: string[];
  topic: string | null;
  importance: number;
  confidence: number | null;
  status: string;
  source_url: string | null;
  created_at: string;
  updated_at: string;
};

type Props = {
  nodes: GraphNode[];
};

export function CardPreviewOverlay({ nodes }: Props) {
  const { selectedNodeIds, clearSelection } = useUniverseStore();

  const selectedId =
    selectedNodeIds.length === 1 ? selectedNodeIds[0] : null;

  const graphNode = selectedId
    ? nodes.find((n) => n.id === selectedId) ?? null
    : null;

  const { data: card, isLoading } = useQuery<ApiCard>({
    queryKey: ["zettels", "card-detail", selectedId],
    queryFn: () =>
      apiFetch<ApiCard>(`${apiRoutes.zettels.cards}/${selectedId}`),
    enabled: selectedId !== null,
    staleTime: 30_000,
  });

  // Close on Escape (handled globally too, but this is belt-and-suspenders)
  useEffect(() => {
    if (!selectedId) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") clearSelection();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedId, clearSelection]);

  if (!selectedId || !graphNode) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="pointer-events-auto fixed inset-0 z-30 bg-black/50 backdrop-blur-sm"
        onClick={clearSelection}
      />

      {/* Modal */}
      <div className="pointer-events-auto fixed inset-0 z-40 flex items-center justify-center p-8">
        <div
          className="relative w-full max-w-lg rounded-xl border border-white/10 bg-[#1a1918] p-6 shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Close button */}
          <button
            onClick={clearSelection}
            className="absolute right-4 top-4 rounded p-1 text-white/30 transition-colors hover:bg-white/5 hover:text-white/60"
          >
            <X className="h-4 w-4" />
          </button>

          {/* Title */}
          <h2 className="pr-8 font-serif text-xl font-semibold text-white">
            {graphNode.title}
          </h2>

          {/* Topic */}
          {graphNode.topic && (
            <span className="mt-2 inline-block font-mono text-sm uppercase tracking-wider text-[#E8590C]">
              {graphNode.topic}
            </span>
          )}

          {/* Tags */}
          {graphNode.tags.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {graphNode.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded bg-white/5 px-2 py-0.5 font-mono text-sm text-white/50"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}

          {/* Content (from API) */}
          {isLoading && (
            <div className="mt-4 flex items-center gap-2">
              <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#E8590C]" />
              <span className="font-mono text-sm text-white/30">Loading...</span>
            </div>
          )}

          {card?.content && (
            <p className="mt-4 max-h-48 overflow-y-auto whitespace-pre-wrap font-sans text-base leading-relaxed text-white/70">
              {card.content}
            </p>
          )}

          {!isLoading && card && !card.content && (
            <p className="mt-4 font-sans text-base italic text-white/30">
              No content yet.
            </p>
          )}

          {/* Metadata row */}
          <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-white/5 pt-3 font-mono text-sm text-white/30">
            <span>{graphNode.degree} connections</span>
            {graphNode.importance > 0 && (
              <span>importance {graphNode.importance}/10</span>
            )}
            {card?.confidence != null && (
              <span>confidence {Math.round(card.confidence * 100)}%</span>
            )}
            {graphNode.status === "stub" && (
              <span className="text-amber-400">stub</span>
            )}
          </div>

          {/* Actions */}
          <div className="mt-4 flex gap-2">
            <a
              href={`/knowledge?card=${selectedId}`}
              className="flex items-center gap-1.5 rounded-lg bg-[#E8590C]/10 px-4 py-2 font-sans text-sm font-medium text-[#E8590C] transition-colors hover:bg-[#E8590C]/20"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Open in Knowledge Hub
            </a>
          </div>
        </div>
      </div>
    </>
  );
}
