"use client";

import { useMemo, useState } from "react";

import { Loader2 } from "lucide-react";

import { useZettelCards } from "@/features/zettels/queries";
import { MOCK_ZETTELS, getDueCount } from "./mock-data";
import { ViewToolbar, type ViewMode } from "./view-toolbar";
import { ZettelCard } from "./zettel-card";
import { ZettelTable } from "./zettel-table";
import { ZettelGraph } from "./zettel-graph";
import { ZettelDetailPanel } from "./zettel-detail-panel";
import { ReviewStation } from "./review-station";

export function KnowledgeHub() {
  const [activeView, setActiveView] = useState<ViewMode>("cards");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: apiZettels, isLoading } = useZettelCards();

  // Use real API data if available, fall back to mock data
  const allZettels = apiZettels && apiZettels.length > 0 ? apiZettels : MOCK_ZETTELS;

  const filtered = useMemo(() => {
    if (!search.trim()) return allZettels;
    const q = search.toLowerCase();
    return allZettels.filter(
      (z) =>
        z.title.toLowerCase().includes(q) ||
        z.tags.some((t) => t.toLowerCase().includes(q)) ||
        z.summary.toLowerCase().includes(q),
    );
  }, [search, allZettels]);

  const selectedZettel = selectedId ? allZettels.find((z) => z.id === selectedId) ?? null : null;
  const dueCount = getDueCount(allZettels);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="px-6 pt-6 pb-4">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="font-serif text-[28px] tracking-tight">Knowledge</h1>
            <p className="mt-1 font-mono text-xs text-[var(--alfred-text-tertiary)]">
              {isLoading ? <Loader2 className="inline size-3 animate-spin" /> : allZettels.length} zettels · {dueCount} due for review
            </p>
          </div>
        </div>
      </div>

      {/* View toolbar */}
      <ViewToolbar
        activeView={activeView}
        onViewChange={setActiveView}
        search={search}
        onSearchChange={setSearch}
      />

      {/* Content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Main view */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-4">
            {activeView === "cards" && (
              <div className="grid gap-3 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
                {filtered.map((z) => (
                  <ZettelCard
                    key={z.id}
                    zettel={z}
                    isSelected={selectedId === z.id}
                    onClick={() => setSelectedId(selectedId === z.id ? null : z.id)}
                  />
                ))}
              </div>
            )}

            {activeView === "table" && (
              <ZettelTable
                zettels={filtered}
                selectedId={selectedId}
                onSelect={(id) => setSelectedId(selectedId === id ? null : id)}
              />
            )}

            {activeView === "graph" && (
              <div className="h-[500px]">
                <ZettelGraph
                  zettels={filtered}
                  selectedId={selectedId}
                  onSelect={(id) => setSelectedId(selectedId === id ? null : id)}
                />
              </div>
            )}

            {activeView === "timeline" && (
              <div className="py-20 text-center">
                <p className="font-serif text-xl text-muted-foreground">Timeline view</p>
                <p className="mt-2 font-mono text-xs text-[var(--alfred-text-tertiary)]">Coming soon</p>
              </div>
            )}

            {filtered.length === 0 && search && (
              <div className="py-20 text-center">
                <p className="font-serif text-xl text-muted-foreground">No matches</p>
                <p className="mt-2 font-mono text-xs text-[var(--alfred-text-tertiary)]">
                  Try a different search term
                </p>
              </div>
            )}
          </div>

          {/* Review Station — below the views */}
          <ReviewStation zettels={MOCK_ZETTELS} />
        </div>

        {/* Detail panel */}
        {selectedZettel && (
          <ZettelDetailPanel
            zettel={selectedZettel}
            onClose={() => setSelectedId(null)}
            onSelectZettel={(id) => setSelectedId(id)}
          />
        )}
      </div>
    </div>
  );
}
