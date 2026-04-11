"use client";

import { useCallback, useRef, useState } from "react";
import { Sparkles, X } from "lucide-react";
import { useUniverseStore } from "@/lib/stores/universe-store";
import { streamSSE } from "@/lib/api/sse";
import { apiRoutes } from "@/lib/api/routes";
import type { GraphNode } from "@/features/universe/queries";

type Props = { nodes: GraphNode[] };

export function AIDiscoveryPanel({ nodes }: Props) {
  const { selectedNodeIds, clearSelection } = useUniverseStore();
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const selectedNodes = selectedNodeIds
    .map((id) => nodes.find((n) => n.id === id))
    .filter(Boolean) as GraphNode[];

  const handleDiscover = useCallback(async () => {
    if (selectedNodes.length < 2) return;

    // Abort any in-flight request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setResponse("");
    setError(null);
    setLoading(true);

    const titles = selectedNodes.map((n) => n.title).join(", ");
    const prompt = `How are these knowledge cards connected? Analyze their relationships, shared themes, and potential synthesis points. Cards: ${titles}`;

    try {
      let result = "";
      await streamSSE(
        apiRoutes.agent.stream,
        {
          message: prompt,
          intent: "discover_connections",
          intent_args: {
            card_ids: selectedNodeIds,
            card_titles: selectedNodes.map((n) => n.title),
          },
          model: "gpt-5.4-mini",
        },
        (event, data) => {
          if (event === "token" && typeof data.content === "string") {
            result += data.content;
            setResponse(result);
          }
          if (event === "error" && typeof data.message === "string") {
            setError(data.message);
          }
        },
        controller.signal,
      );
    } catch (err: any) {
      if (err.name !== "AbortError") {
        setError(err.message || "Failed to connect to AI agent");
      }
    } finally {
      setLoading(false);
    }
  }, [selectedNodes, selectedNodeIds]);

  if (selectedNodeIds.length < 2) return null;

  return (
    <div className="pointer-events-auto absolute bottom-6 left-1/2 z-20 w-full max-w-lg -translate-x-1/2">
      <div className="rounded-xl border border-white/10 bg-[#1a1918]/95 p-4 shadow-2xl backdrop-blur-sm">
        {/* Header */}
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5 text-[#E8590C]" />
            <span className="font-mono text-[10px] uppercase tracking-wider text-white/50">
              AI Discovery
            </span>
          </div>
          <button
            onClick={clearSelection}
            className="rounded p-1 text-white/30 transition-colors hover:bg-white/5 hover:text-white/60"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Selected cards */}
        <div className="mb-3 flex flex-wrap gap-1.5">
          {selectedNodes.map((node) => (
            <span
              key={node.id}
              className="rounded-sm bg-white/5 px-2 py-0.5 font-mono text-[10px] text-white/60"
            >
              {node.title}
            </span>
          ))}
        </div>

        {/* Action button */}
        {!response && !loading && (
          <button
            onClick={handleDiscover}
            className="w-full rounded-lg bg-[#E8590C]/10 px-4 py-2 font-sans text-xs font-medium text-[#E8590C] transition-colors hover:bg-[#E8590C]/20"
          >
            How are these connected?
          </button>
        )}

        {/* Loading state */}
        {loading && !response && (
          <div className="flex items-center gap-2 py-2">
            <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#E8590C]" />
            <span className="font-mono text-[10px] text-white/40">
              Analyzing connections...
            </span>
          </div>
        )}

        {/* AI Response */}
        {response && (
          <div className="mt-1 max-h-48 overflow-y-auto">
            <p className="whitespace-pre-wrap font-sans text-xs leading-relaxed text-white/70">
              {response}
            </p>
            {loading && (
              <span className="inline-block h-3 w-1 animate-pulse bg-[#E8590C]/60" />
            )}
          </div>
        )}

        {/* Error state */}
        {error && (
          <p className="mt-2 font-mono text-[10px] text-red-400/80">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
