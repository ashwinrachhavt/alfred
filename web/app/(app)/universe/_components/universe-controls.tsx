"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Search, Volume2, VolumeX, Play, Pause } from "lucide-react";
import type { GraphNode } from "@/features/universe/queries";
import { useUniverseStore } from "@/lib/stores/universe-store";

type PositionedGraphNode = GraphNode & { x?: number; y?: number; z?: number };

type Props = {
  nodes: PositionedGraphNode[];
  flyToNode: (node: PositionedGraphNode, distance?: number, duration?: number) => void;
};

export function UniverseControls({ nodes, flyToNode }: Props) {
  const {
    audioEnabled,
    toggleAudio,
    selectNode,
    clearSelection,
    isTimeLapsePlaying,
    setTimeLapsePlaying,
  } = useUniverseStore();

  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Live fuzzy search results
  const results =
    query.trim().length > 0
      ? nodes
          .filter((n) =>
            n.title.toLowerCase().includes(query.toLowerCase()),
          )
          .slice(0, 8)
      : [];

  // Reset active index when results change
  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  // Open dropdown when there are results
  useEffect(() => {
    setIsOpen(results.length > 0 && query.trim().length > 0);
  }, [results.length, query]);

  // Scroll active item into view
  useEffect(() => {
    if (!listRef.current) return;
    const item = listRef.current.children[activeIndex] as HTMLElement | undefined;
    item?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  const navigateToNode = useCallback(
    (node: PositionedGraphNode) => {
      clearSelection();
      selectNode(node.id);
      flyToNode(node, 80, 600);
      setQuery("");
      setIsOpen(false);
      inputRef.current?.blur();
    },
    [selectNode, clearSelection, flyToNode],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!isOpen || results.length === 0) {
        if (e.key === "Escape") {
          setQuery("");
          setIsOpen(false);
          inputRef.current?.blur();
        }
        return;
      }

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setActiveIndex((i) => Math.min(i + 1, results.length - 1));
          break;
        case "ArrowUp":
          e.preventDefault();
          setActiveIndex((i) => Math.max(i - 1, 0));
          break;
        case "Enter":
          e.preventDefault();
          if (results[activeIndex]) navigateToNode(results[activeIndex]);
          break;
        case "Escape":
          e.preventDefault();
          setQuery("");
          setIsOpen(false);
          inputRef.current?.blur();
          break;
      }
    },
    [isOpen, results, activeIndex, navigateToNode],
  );

  // Highlight matching substring
  const highlightMatch = (title: string) => {
    if (!query.trim()) return title;
    const idx = title.toLowerCase().indexOf(query.toLowerCase());
    if (idx === -1) return title;
    return (
      <>
        {title.slice(0, idx)}
        <span className="text-[#E8590C]">{title.slice(idx, idx + query.length)}</span>
        {title.slice(idx + query.length)}
      </>
    );
  };

  return (
    <div className="pointer-events-auto absolute left-4 top-4 z-10 flex items-center gap-2">
      {/* Search with live dropdown */}
      <div className="relative">
        <div className="flex items-center gap-2 rounded-full border border-white/10 bg-black/40 px-3 py-2 backdrop-blur-sm">
          <Search className="h-3.5 w-3.5 text-white/40" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => results.length > 0 && setIsOpen(true)}
            onBlur={() => {
              // Delay close so click on result registers
              setTimeout(() => setIsOpen(false), 150);
            }}
            placeholder="Search cards... (⌘K)"
            className="w-48 bg-transparent font-sans text-xs text-white/80 placeholder:text-white/30 focus:outline-none"
          />
          {query && (
            <button
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                setQuery("");
                setIsOpen(false);
              }}
              className="text-white/30 hover:text-white/60"
            >
              <span className="font-mono text-[10px]">×</span>
            </button>
          )}
        </div>

        {/* Results dropdown */}
        {isOpen && results.length > 0 && (
          <div
            ref={listRef}
            className="absolute left-0 top-full mt-1 max-h-64 w-72 overflow-y-auto rounded-lg border border-white/10 bg-[#1a1918]/95 py-1 shadow-2xl backdrop-blur-sm"
          >
            {results.map((node, i) => (
              <button
                key={node.id}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => navigateToNode(node)}
                onMouseEnter={() => setActiveIndex(i)}
                className={`flex w-full flex-col px-3 py-2 text-left transition-colors ${
                  i === activeIndex
                    ? "bg-white/5"
                    : "hover:bg-white/[0.03]"
                }`}
              >
                <span className="truncate font-sans text-xs text-white/80">
                  {highlightMatch(node.title)}
                </span>
                <div className="mt-0.5 flex items-center gap-2">
                  {node.topic && (
                    <span className="font-mono text-[9px] uppercase tracking-wider text-[#E8590C]/60">
                      {node.topic}
                    </span>
                  )}
                  <span className="font-mono text-[9px] text-white/25">
                    {node.degree} links
                  </span>
                  {node.tags.length > 0 && (
                    <span className="truncate font-mono text-[9px] text-white/20">
                      {node.tags.slice(0, 3).join(", ")}
                    </span>
                  )}
                </div>
              </button>
            ))}
            <div className="border-t border-white/5 px-3 py-1.5">
              <span className="font-mono text-[9px] text-white/20">
                ↑↓ navigate · enter select · esc close
              </span>
            </div>
          </div>
        )}

        {/* No results */}
        {isOpen && query.trim().length > 0 && results.length === 0 && (
          <div className="absolute left-0 top-full mt-1 w-72 rounded-lg border border-white/10 bg-[#1a1918]/95 px-3 py-3 shadow-2xl backdrop-blur-sm">
            <span className="font-sans text-xs text-white/30">
              No cards matching &ldquo;{query}&rdquo;
            </span>
          </div>
        )}
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
