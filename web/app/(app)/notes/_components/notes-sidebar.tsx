"use client";

import { useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FilePlus2,
  PanelLeftClose,
  Search,
  Trash2,
  Upload,
} from "lucide-react";

import type { NoteTreeResponse, Workspace } from "@/lib/api/types/notes";

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

type NotesSidebarProps = {
  workspace: Workspace | null;
  tree: NoteTreeResponse | null;
  selectedNoteId: string | null;
  search: string;
  onSearchChange: (next: string) => void;
  onSelectNoteId: (noteId: string) => void;
  onCreateNote: () => void;
  onImportMarkdown: () => void;
  onCollapse: () => void;
  onDeleteNote?: (noteId: string) => void;
  isLoading?: boolean;
};

type TreeNode = NoteTreeResponse["items"][number];

function findAncestorIds(nodes: TreeNode[], targetId: string): string[] | null {
  for (const node of nodes) {
    if (node.note.id === targetId) {
      return [];
    }

    const childAncestors = findAncestorIds(node.children, targetId);
    if (childAncestors !== null) {
      return [node.note.id, ...childAncestors];
    }
  }

  return null;
}

function matchesQuery(title: string, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return title.toLowerCase().includes(q);
}

function filterTree(nodes: TreeNode[], query: string): TreeNode[] {
  if (!query.trim()) return nodes;
  const filtered: TreeNode[] = [];

  for (const node of nodes) {
    const children = filterTree(node.children, query);
    if (matchesQuery(node.note.title, query) || children.length) {
      filtered.push({ ...node, children });
    }
  }
  return filtered;
}

function TreeList({
  nodes,
  depth,
  collapsedBranches,
  selectedAncestorIds,
  searchActive,
  selectedNoteId,
  onToggleExpanded,
  onSelectNoteId,
  onRequestDelete,
}: {
  nodes: TreeNode[];
  depth: number;
  collapsedBranches: Record<string, boolean>;
  selectedAncestorIds: Set<string>;
  searchActive: boolean;
  selectedNoteId: string | null;
  onToggleExpanded: (noteId: string) => void;
  onSelectNoteId: (noteId: string) => void;
  onRequestDelete?: (noteId: string, title: string) => void;
}) {
  return (
    <ul className="space-y-0.5">
      {nodes.map((node) => {
        const isBranch = node.children.length > 0;
        const isSelected = selectedNoteId === node.note.id;
        const isExpanded =
          isBranch &&
          (searchActive ||
            selectedAncestorIds.has(node.note.id) ||
            !collapsedBranches[node.note.id]);
        const icon = node.note.icon?.trim() || (isBranch ? "📁" : "📄");

        return (
          <li key={node.note.id} className="group/note relative">
            <div className="flex items-center" style={{ paddingLeft: `${depth * 12}px` }}>
              {isBranch ? (
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground shrink-0 rounded p-1 transition-colors hover:bg-[var(--alfred-accent-subtle)]"
                  onClick={() => onToggleExpanded(node.note.id)}
                  aria-label={`${isExpanded ? "Collapse" : "Expand"} ${node.note.title || "Untitled"}`}
                >
                  {isExpanded ? (
                    <ChevronDown className="size-3.5" aria-hidden="true" />
                  ) : (
                    <ChevronRight className="size-3.5" aria-hidden="true" />
                  )}
                </button>
              ) : (
                <span className="size-6 shrink-0" aria-hidden="true" />
              )}

              <button
                type="button"
                className={cn(
                  "flex min-w-0 flex-1 items-center gap-2 truncate rounded-md px-2 py-1.5 text-left text-sm transition-colors",
                  isSelected
                    ? "border-primary text-foreground border-l-2 bg-[var(--alfred-accent-subtle)]"
                    : "text-muted-foreground hover:text-foreground border-l-2 border-transparent hover:bg-[var(--alfred-accent-subtle)]",
                )}
                onClick={() => onSelectNoteId(node.note.id)}
              >
                <span className="text-sm" aria-hidden="true">
                  {icon}
                </span>
                <span className="truncate">{node.note.title || "Untitled"}</span>
              </button>

              {onRequestDelete && (
                <button
                  type="button"
                  className="text-muted-foreground/0 group-hover/note:text-muted-foreground/60 mr-1 shrink-0 rounded p-1 transition-colors hover:!text-[var(--error)]"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRequestDelete(node.note.id, node.note.title || "Untitled");
                  }}
                  aria-label="Delete note"
                  title="Delete note"
                >
                  <Trash2 className="size-3.5" />
                </button>
              )}
            </div>

            {isBranch && isExpanded ? (
              <div className="pt-0.5">
                <TreeList
                  nodes={node.children}
                  depth={depth + 1}
                  collapsedBranches={collapsedBranches}
                  selectedAncestorIds={selectedAncestorIds}
                  searchActive={searchActive}
                  selectedNoteId={selectedNoteId}
                  onToggleExpanded={onToggleExpanded}
                  onSelectNoteId={onSelectNoteId}
                  onRequestDelete={onRequestDelete}
                />
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

export function NotesSidebar({
  workspace,
  tree,
  selectedNoteId,
  search,
  onSearchChange,
  onSelectNoteId,
  onCreateNote,
  onImportMarkdown,
  onCollapse,
  onDeleteNote,
  isLoading,
}: NotesSidebarProps) {
  const nodes = useMemo(() => tree?.items ?? [], [tree]);
  const filtered = useMemo(() => filterTree(nodes, search), [nodes, search]);
  const selectedAncestorIds = useMemo(() => {
    if (!selectedNoteId) {
      return [];
    }

    return findAncestorIds(nodes, selectedNoteId) ?? [];
  }, [nodes, selectedNoteId]);
  const selectedAncestorSet = useMemo(() => new Set(selectedAncestorIds), [selectedAncestorIds]);
  const [collapsedBranches, setCollapsedBranches] = useState<Record<string, boolean>>({});
  const isSearchActive = search.trim().length > 0;

  const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null);

  const handleConfirmDelete = () => {
    if (deleteTarget && onDeleteNote) {
      onDeleteNote(deleteTarget.id);
    }
    setDeleteTarget(null);
  };

  return (
    <aside className="bg-card flex h-full min-h-0 flex-col border-r">
      <header className="flex items-center justify-between gap-2 border-b p-3">
        <div className="min-w-0">
          <p className="truncate text-lg">
            {workspace ? `${workspace.icon ?? "📓"} ${workspace.name}` : "Notes"}
          </p>
          <p className="truncate text-[10px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
            Markdown-first pages
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button type="button" size="icon-sm" variant="ghost" onClick={onCollapse}>
            <PanelLeftClose className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">Collapse notes sidebar</span>
          </Button>
          <Button type="button" size="icon-sm" variant="outline" onClick={onImportMarkdown}>
            <Upload className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">Import markdown</span>
          </Button>
          <Button type="button" size="icon" variant="outline" onClick={onCreateNote}>
            <FilePlus2 className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">New note</span>
          </Button>
        </div>
      </header>

      <div className="px-3 py-3">
        <div className="relative">
          <Search
            className="text-muted-foreground absolute top-2.5 left-2 h-4 w-4"
            aria-hidden="true"
          />
          <Input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search notes..."
            className="pl-8"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {isLoading ? (
          <div className="space-y-2 px-1">
            <Skeleton className="h-7 w-11/12" />
            <Skeleton className="h-7 w-9/12" />
            <Skeleton className="h-7 w-10/12" />
            <Skeleton className="h-7 w-8/12" />
          </div>
        ) : filtered.length ? (
          <TreeList
            nodes={filtered}
            depth={0}
            collapsedBranches={collapsedBranches}
            selectedAncestorIds={selectedAncestorSet}
            searchActive={isSearchActive}
            selectedNoteId={selectedNoteId}
            onToggleExpanded={(noteId) =>
              setCollapsedBranches((previous) => {
                const next = { ...previous };

                if (previous[noteId]) {
                  delete next[noteId];
                } else {
                  next[noteId] = true;
                }

                return next;
              })
            }
            onSelectNoteId={onSelectNoteId}
            onRequestDelete={
              onDeleteNote ? (id, title) => setDeleteTarget({ id, title }) : undefined
            }
          />
        ) : (
          <EmptyState
            title={nodes.length ? "No matches" : "No notes yet"}
            description={
              nodes.length ? "Try a different search." : "Create your first note to get started."
            }
            action={
              <Button type="button" onClick={onCreateNote} className="text-xs">
                New note
              </Button>
            }
          />
        )}
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="">Delete note</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &ldquo;{deleteTarget?.title}&rdquo;? This action
              cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="ghost" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleConfirmDelete} className="text-xs">
              <Trash2 className="mr-1.5 size-3.5" />
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  );
}
