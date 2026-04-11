"use client";

import { useCallback, useState } from "react";
import { Search, Volume2, VolumeX, Play, Pause } from "lucide-react";
import type { GraphNode } from "@/features/universe/queries";
import { useUniverseStore } from "@/lib/stores/universe-store";

type Props = { nodes: GraphNode[]; graphRef: React.RefObject<any> };

export function UniverseControls({ nodes, graphRef }: Props) {
  const {
    audioEnabled,
    toggleAudio,
    selectNode,
    clearSelection,
    isTimeLapsePlaying,
    setTimeLapsePlaying,
  } = useUniverseStore();
  const [query, setQuery] = useState("");

  const handleSearch = useCallback(() => {
    if (!query.trim() || !graphRef.current) return;
    const match = nodes.find((n) =>
      n.title.toLowerCase().includes(query.toLowerCase()),
    );
    if (match) {
      clearSelection();
      selectNode(match.id);
      const fgNode = graphRef.current
        .graphData()
        .nodes.find((n: any) => n.id === match.id);
      if (fgNode) {
        graphRef.current.cameraPosition(
          { x: fgNode.x + 80, y: fgNode.y + 80, z: fgNode.z + 80 },
          { x: fgNode.x, y: fgNode.y, z: fgNode.z },
          1500,
        );
      }
    }
  }, [query, nodes, graphRef, selectNode, clearSelection]);

  return (
    <div className="pointer-events-auto absolute left-4 top-4 z-10 flex items-center gap-2">
      <div className="flex items-center gap-2 rounded-full border border-white/10 bg-black/40 px-3 py-2 backdrop-blur-sm">
        <Search className="h-3.5 w-3.5 text-white/40" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Search cards..."
          className="w-40 bg-transparent font-sans text-xs text-white/80 placeholder:text-white/30 focus:outline-none"
        />
      </div>

      {/* Time-lapse play/pause */}
      <button
        onClick={() => setTimeLapsePlaying(!isTimeLapsePlaying)}
        className="rounded-full border border-white/10 bg-black/40 p-2 backdrop-blur-sm"
        title={isTimeLapsePlaying ? "Pause time-lapse" : "Play time-lapse (Space)"}
      >
        {isTimeLapsePlaying ? (
          <Pause className="h-3.5 w-3.5 text-[#E8590C]" />
        ) : (
          <Play className="h-3.5 w-3.5 text-white/40" />
        )}
      </button>

      {/* Audio toggle */}
      <button
        onClick={toggleAudio}
        className="rounded-full border border-white/10 bg-black/40 p-2 backdrop-blur-sm"
        title={audioEnabled ? "Mute" : "Sound"}
      >
        {audioEnabled ? (
          <Volume2 className="h-3.5 w-3.5 text-white/40" />
        ) : (
          <VolumeX className="h-3.5 w-3.5 text-white/40" />
        )}
      </button>

      <div className="rounded-full border border-white/10 bg-black/40 px-3 py-2 backdrop-blur-sm">
        <span className="font-mono text-[10px] text-white/40">
          {nodes.length} cards
        </span>
      </div>
    </div>
  );
}
