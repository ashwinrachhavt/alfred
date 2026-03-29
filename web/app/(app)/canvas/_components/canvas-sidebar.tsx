"use client";

import { useMemo, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { Layers, Plus, Search, Trash2 } from "lucide-react";

import type { Whiteboard } from "@/features/canvas/queries";

import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type CanvasSidebarProps = {
  canvases: Whiteboard[];
  selectedCanvasId: number | null;
  search: string;
  onSearchChange: (next: string) => void;
  onSelectCanvas: (id: number) => void;
  onCreateCanvas: () => void;
  onDeleteCanvas?: (id: number) => void;
  isLoading?: boolean;
};

function matchesQuery(title: string, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return title.toLowerCase().includes(q);
}

export function CanvasSidebar({
  canvases,
  selectedCanvasId,
  search,
  onSearchChange,
  onSelectCanvas,
  onCreateCanvas,
  onDeleteCanvas,
  isLoading,
}: CanvasSidebarProps) {
  const filtered = useMemo(
    () => canvases.filter((c) => matchesQuery(c.title, search)),
    [canvases, search],
  );

  const [deleteTarget, setDeleteTarget] = useState<{ id: number; title: string } | null>(null);

  const handleConfirmDelete = () => {
    if (deleteTarget && onDeleteCanvas) {
      onDeleteCanvas(deleteTarget.id);
    }
    setDeleteTarget(null);
  };

  return (
    <aside className="flex h-full min-h-0 flex-col border-r bg-card">
      <header className="flex items-center justify-between gap-2 border-b p-3">
        <div className="min-w-0">
          <p className="truncate font-serif text-lg">Canvases</p>
          <p className="truncate font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
            Excalidraw whiteboards
          </p>
        </div>
        <Button type="button" size="icon" variant="outline" onClick={onCreateCanvas}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          <span className="sr-only">New canvas</span>
        </Button>
      </header>

      <div className="px-3 py-3">
        <div className="relative">
          <Search className="absolute top-2.5 left-2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
          <Input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search canvases..."
            className="pl-8"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {isLoading ? (
          <div className="space-y-2 px-1">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : filtered.length ? (
          <ul className="space-y-1">
            {filtered.map((canvas) => {
              const isSelected = selectedCanvasId === canvas.id;
              const timeAgo = canvas.updated_at
                ? formatDistanceToNow(new Date(canvas.updated_at), { addSuffix: true })
                : null;

              return (
                <li key={canvas.id} className="group/canvas relative">
                  <button
                    type="button"
                    className={cn(
                      "flex w-full flex-col gap-0.5 rounded-md px-3 py-2 text-left transition-colors",
                      isSelected
                        ? "border-l-2 border-primary bg-[var(--alfred-accent-subtle)] text-foreground"
                        : "border-l-2 border-transparent text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
                    )}
                    onClick={() => onSelectCanvas(canvas.id)}
                  >
                    <span className="flex items-center gap-2">
                      <Layers className="size-3.5 shrink-0 opacity-60" />
                      <span className="truncate text-sm font-medium">
                        {canvas.title || "Untitled Canvas"}
                      </span>
                    </span>
                    {timeAgo && (
                      <span className="ml-5 font-mono text-[10px] text-[var(--alfred-text-tertiary)]">
                        {timeAgo}
                      </span>
                    )}
                  </button>

                  {onDeleteCanvas && (
                    <button
                      type="button"
                      className="absolute top-2 right-2 shrink-0 rounded p-1 transition-colors text-muted-foreground/0 group-hover/canvas:text-muted-foreground/60 hover:!text-[var(--error)]"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteTarget({ id: canvas.id, title: canvas.title });
                      }}
                      aria-label="Delete canvas"
                      title="Delete canvas"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <EmptyState
            title={canvases.length ? "No matches" : "No canvases yet"}
            description={
              canvases.length
                ? "Try a different search."
                : "Create your first canvas to start brainstorming."
            }
            action={
              <Button type="button" onClick={onCreateCanvas} className="font-mono text-xs">
                <Plus className="mr-1.5 h-4 w-4" />
                New canvas
              </Button>
            }
          />
        )}
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-serif">Delete canvas</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &ldquo;{deleteTarget?.title}&rdquo;? This will archive the canvas.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="ghost" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              className="font-mono text-xs"
            >
              <Trash2 className="mr-1.5 size-3.5" />
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  );
}
