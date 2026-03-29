"use client";

import { useCallback, useMemo, useRef, useState } from "react";

import { Loader2, Plus, Sparkles as SparklesIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useZettelCards } from "@/features/zettels/queries";
import { MOCK_ZETTELS, getDueCount } from "./mock-data";
import { ViewToolbar, type ViewMode } from "./view-toolbar";
import { ZettelCard } from "./zettel-card";
import { ZettelTable } from "./zettel-table";
import { ZettelGraph } from "./zettel-graph";
import { ZettelDetailPanel } from "./zettel-detail-panel";
import { ReviewStation } from "./review-station";
import { CreateZettelDialog } from "./create-zettel-dialog";
import { AIGenerateDialog } from "./ai-generate-dialog";

export function KnowledgeHub() {
  const [activeView, setActiveView] = useState<ViewMode>("cards");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pulsingId, setPulsingId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showAIGenerate, setShowAIGenerate] = useState(false);

  const cardRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

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

  const handleSelectZettel = useCallback((id: string) => {
    setSelectedId(id);
    setPulsingId(id);

    // Scroll to the card in cards view
    requestAnimationFrame(() => {
      const el = cardRefs.current.get(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });

    // Clear pulse after animation completes
    setTimeout(() => setPulsingId(null), 1600);
  }, []);

  const setCardRef = useCallback((id: string, el: HTMLButtonElement | null) => {
    if (el) {
      cardRefs.current.set(id, el);
    } else {
      cardRefs.current.delete(id);
    }
  }, []);

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
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              className="gap-1.5 font-mono text-xs"
              onClick={() => setShowAIGenerate(true)}
            >
              <SparklesIcon className="size-3.5" />
              AI Generate
            </Button>
            <Button
              size="sm"
              className="gap-1.5 font-mono text-xs"
              onClick={() => setShowCreate(true)}
            >
              <Plus className="size-3.5" />
              New Zettel
            </Button>
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
                    ref={(el) => setCardRef(z.id, el)}
                    zettel={z}
                    isSelected={selectedId === z.id}
                    isPulsing={pulsingId === z.id}
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
            allZettels={allZettels}
            onClose={() => setSelectedId(null)}
            onSelectZettel={handleSelectZettel}
          />
        )}
      </div>

      {/* Dialogs */}
      <CreateZettelDialog open={showCreate} onOpenChange={setShowCreate} />
      <AIGenerateDialog open={showAIGenerate} onOpenChange={setShowAIGenerate} />
    </div>
  );
}
