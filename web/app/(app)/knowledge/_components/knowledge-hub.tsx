"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AlertCircle, BookOpen, Layers, Loader2, Play, Plus, RefreshCw, Sparkles as SparklesIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useZettelCards, useZettelTopics, useZettelTags } from "@/features/zettels/queries";
import { useTaskTracker } from "@/features/tasks/task-tracker-provider";
import { apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { getDueCount } from "./mock-data";
import { FilterBar, type ZettelFilters } from "./filter-bar";
import { ViewToolbar, type ViewMode } from "./view-toolbar";
import { ZettelCard } from "./zettel-card";
import { ZettelTable } from "./zettel-table";
import { ZettelGraph } from "./zettel-graph";
import { ZettelTimeline } from "./zettel-timeline";
import { ZettelDetailPanel } from "./zettel-detail-panel";
import { ReviewStation } from "./review-station";
import { CreateZettelDialog } from "./create-zettel-dialog";
import { AIGenerateDialog } from "./ai-generate-dialog";
import { BulkCreateDialog } from "./bulk-create-dialog";

function CardSkeleton() {
 return (
 <div className="flex flex-col rounded-lg border p-4 space-y-3">
 <Skeleton className="h-5 w-3/4" />
 <Skeleton className="h-4 w-full" />
 <Skeleton className="h-4 w-2/3" />
 <div className="flex gap-2 pt-1">
 <Skeleton className="h-5 w-16 rounded-sm" />
 <Skeleton className="h-5 w-12 rounded-sm" />
 <Skeleton className="ml-auto h-5 w-8" />
 </div>
 </div>
 );
}

function EmptyState({ onCreateClick, onAIClick }: { onCreateClick: () => void; onAIClick: () => void }) {
 return (
 <div className="flex flex-col items-center justify-center py-24 px-4">
 <div className="flex size-16 items-center justify-center rounded-xl border-2 border-dashed border-[var(--border-strong)]">
 <BookOpen className="size-7 text-[var(--alfred-text-tertiary)]" />
 </div>
 <h2 className="mt-5 text-xl">Your knowledge starts here</h2>
 <p className="mt-2 max-w-sm text-center text-[13px] leading-relaxed text-muted-foreground">
 Create your first zettel to begin building your knowledge graph. Each zettel is an atomic
 idea that connects to others over time.
 </p>
 <div className="mt-6 flex gap-3">
 <Button size="sm" className="gap-1.5 text-xs" onClick={onCreateClick}>
 <Plus className="size-3.5" />
 New Zettel
 </Button>
 <Button size="sm" variant="outline" className="gap-1.5 text-xs" onClick={onAIClick}>
 <SparklesIcon className="size-3.5" />
 AI Generate
 </Button>
 </div>
 </div>
 );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
 return (
 <div className="flex flex-col items-center justify-center py-24 px-4">
 <div className="flex size-14 items-center justify-center rounded-xl border border-destructive/30 bg-destructive/10">
 <AlertCircle className="size-6 text-destructive" />
 </div>
 <h2 className="mt-4 text-lg">Something went wrong</h2>
 <p className="mt-1.5 text-[13px] text-muted-foreground">
 Could not load your zettels. Check your connection and try again.
 </p>
 <Button size="sm" variant="outline" className="mt-4 text-xs" onClick={onRetry}>
 Try again
 </Button>
 </div>
 );
}

export function KnowledgeHub() {
 const [activeView, setActiveView] = useState<ViewMode>("cards");
 const [filters, setFilters] = useState<ZettelFilters>({});
 const [selectedId, setSelectedId] = useState<string | null>(null);
 const [pulsingId, setPulsingId] = useState<string | null>(null);
 const [showCreate, setShowCreate] = useState(false);
 const [showAIGenerate, setShowAIGenerate] = useState(false);
 const [showBulkCreate, setShowBulkCreate] = useState(false);
 const [workflowLoading, setWorkflowLoading] = useState<string | null>(null);

 const { trackTask } = useTaskTracker();
 const cardRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

 // Server-side allZettels data
 const { data: allZettels = [], isLoading, isError, refetch } = useZettelCards(filters);
 const { data: availableTopics = [] } = useZettelTopics();
 const { data: availableTags = [] } = useZettelTags();

 const selectedZettel = selectedId ? allZettels.find((z) => z.id === selectedId) ?? null : null;
 const dueCount = getDueCount(allZettels);

 // Close detail panel if selected zettel gets allZettels out
 useEffect(() => {
 if (selectedId && !allZettels.some((z) => z.id === selectedId) && (filters.q || filters.topic || filters.tags?.length)) {
 setSelectedId(null);
 }
 }, [allZettels, selectedId, filters]);

 const handleSelectZettel = useCallback((id: string) => {
 setSelectedId(id);
 setPulsingId(id);

 requestAnimationFrame(() => {
 const el = cardRefs.current.get(id);
 if (el) {
 el.scrollIntoView({ behavior: "smooth", block: "center" });
 }
 });

 setTimeout(() => setPulsingId(null), 1600);
 }, []);

 const setCardRef = useCallback((id: string, el: HTMLButtonElement | null) => {
 if (el) {
 cardRefs.current.set(id, el);
 } else {
 cardRefs.current.delete(id);
 }
 }, []);

 // Keyboard navigation
 const handleKeyDown = useCallback(
 (e: React.KeyboardEvent) => {
 // Escape deselects in ALL views
 if (e.key === "Escape") {
 setSelectedId(null);
 return;
 }

 // Arrow navigation for cards view only
 if (activeView !== "cards" || allZettels.length === 0) return;
 const currentIndex = selectedId ? allZettels.findIndex((z) => z.id === selectedId) : -1;

 if (e.key === "ArrowRight" || e.key === "ArrowDown") {
 e.preventDefault();
 const next = Math.min(currentIndex + 1, allZettels.length - 1);
 handleSelectZettel(allZettels[next].id);
 } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
 e.preventDefault();
 const prev = Math.max(currentIndex - 1, 0);
 handleSelectZettel(allZettels[prev].id);
 }
 },
 [activeView, allZettels, selectedId, handleSelectZettel],
 );

 const triggerWorkflow = useCallback(async (key: string, label: string, fn: () => Promise<{ task_id: string }>) => {
   if (workflowLoading) return;
   setWorkflowLoading(key);
   try {
     const res = await fn();
     if (res.task_id) {
       trackTask({ id: res.task_id, label, source: "generic" });
     }
   } catch {
     // silently fail — toast from task tracker will handle errors
   } finally {
     setWorkflowLoading(null);
   }
 }, [workflowLoading, trackTask]);

 const handleReclassifyAll = useCallback(() => {
   triggerWorkflow("reclassify", "Reclassify All", () =>
     apiPostJson<{ task_id: string }, Record<string, never>>(apiRoutes.taxonomy.reclassifyAll, {})
   );
 }, [triggerWorkflow]);

 const handleReplayBatch = useCallback(() => {
   triggerWorkflow("enrich", "Bulk Enrich", async () => {
     const res = await apiPostJson<{ queued: number; tasks: { doc_id: string; task_id: string }[] }, Record<string, never>>(
       apiRoutes.pipeline.replayBatch, {}
     );
     // Track the first task as a representative
     const firstTask = res.tasks?.[0];
     return { task_id: firstTask?.task_id ?? "" };
   });
 }, [triggerWorkflow]);

 return (
 // eslint-disable-next-line jsx-a11y/no-static-element-interactions
 <div className="flex h-full flex-col" onKeyDown={handleKeyDown} tabIndex={-1}>
 {/* Header */}
 <div className="px-6 pt-6 pb-4">
 <div className="flex items-start justify-between">
 <div>
 <h1 className="text-[28px] tracking-tight">Knowledge</h1>
 <p className="mt-1 text-xs text-[var(--alfred-text-tertiary)]">
 {isLoading ? (
 <Loader2 className="inline size-3 animate-spin" />
 ) : (
 allZettels.length
 )}{" "}
 zettels · {dueCount} due for review
 </p>
 </div>
 <div className="flex items-center gap-2">
 <Button
 size="sm"
 variant="ghost"
 className="gap-1.5 text-xs text-muted-foreground"
 onClick={handleReplayBatch}
 disabled={workflowLoading === "enrich"}
 >
 {workflowLoading === "enrich" ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
 Bulk Enrich
 </Button>
 <Button
 size="sm"
 variant="ghost"
 className="gap-1.5 text-xs text-muted-foreground"
 onClick={handleReclassifyAll}
 disabled={workflowLoading === "reclassify"}
 >
 {workflowLoading === "reclassify" ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
 Reclassify
 </Button>
 <Button
 size="sm"
 variant="outline"
 className="gap-1.5 text-xs"
 onClick={() => setShowBulkCreate(true)}
 >
 <Layers className="size-3.5" />
 Bulk Create
 </Button>
 <Button
 size="sm"
 variant="outline"
 className="gap-1.5 text-xs"
 onClick={() => setShowAIGenerate(true)}
 >
 <SparklesIcon className="size-3.5" />
 AI Generate
 </Button>
 <Button
 size="sm"
 className="gap-1.5 text-xs"
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
 search={filters.q || ""}
 onSearchChange={(v) => setFilters((f) => ({ ...f, q: v || undefined }))}
 />

 {/* Filter bar */}
 <FilterBar
 filters={filters}
 onFiltersChange={setFilters}
 availableTopics={availableTopics}
 availableTags={availableTags}
 />

 {/* Content area */}
 <div className="flex flex-1 overflow-hidden">
 {/* Main view */}
 <div className="flex-1 overflow-y-auto">
 <div className="p-4">
 {/* Loading state */}
 {isLoading && (
 <div className="grid gap-3 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
 {Array.from({ length: 6 }).map((_, i) => (
 <CardSkeleton key={i} />
 ))}
 </div>
 )}

 {/* Error state */}
 {isError && !isLoading && <ErrorState onRetry={() => refetch()} />}

 {/* Empty state */}
 {!isLoading && !isError && allZettels.length === 0 && (
 <EmptyState
 onCreateClick={() => setShowCreate(true)}
 onAIClick={() => setShowAIGenerate(true)}
 />
 )}

 {/* Content views */}
 {!isLoading && !isError && allZettels.length > 0 && (
 <>
 {activeView === "cards" && (
 <div className="grid gap-3 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
 {allZettels.map((z) => (
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
 zettels={allZettels}
 selectedId={selectedId}
 onSelect={(id) => setSelectedId(selectedId === id ? null : id)}
 />
 )}

 {activeView === "graph" && (
 <div className="h-[500px]">
 <ZettelGraph
 zettels={allZettels}
 selectedId={selectedId}
 onSelect={(id) => setSelectedId(selectedId === id ? null : id)}
 />
 </div>
 )}

 {activeView === "timeline" && (
 <ZettelTimeline
 zettels={allZettels}
 selectedId={selectedId}
 onSelect={(id) => setSelectedId(selectedId === id ? null : id)}
 />
 )}

 {allZettels.length === 0 && (filters.q || filters.topic || filters.tags?.length || filters.importance_min) && (
 <div className="py-20 text-center">
 <p className="text-xl text-muted-foreground">No matches</p>
 <p className="mt-2 text-xs text-[var(--alfred-text-tertiary)]">
 Try adjusting your filters
 </p>
 </div>
 )}
 </>
 )}
 </div>

 {/* Review Station */}
 {allZettels.length > 0 && <ReviewStation zettels={allZettels} />}
 </div>

 {/* Detail panel */}
 {selectedZettel && (
 <div className="animate-in slide-in-from-right-4 duration-200 ease-out">
 <ZettelDetailPanel
 zettel={selectedZettel}
 allZettels={allZettels}
 onClose={() => setSelectedId(null)}
 onSelectZettel={handleSelectZettel}
 />
 </div>
 )}
 </div>

 {/* Dialogs */}
 <CreateZettelDialog open={showCreate} onOpenChange={setShowCreate} />
 <AIGenerateDialog open={showAIGenerate} onOpenChange={setShowAIGenerate} />
 <BulkCreateDialog open={showBulkCreate} onOpenChange={setShowBulkCreate} />
 </div>
 );
}
