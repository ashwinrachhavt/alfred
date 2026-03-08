"use client";

import { useMemo } from "react";
import { FilePlus2, Search } from "lucide-react";

import type { NoteTreeResponse, Workspace } from "@/lib/api/types/notes";

import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

type NotesSidebarProps = {
  workspace: Workspace | null;
  tree: NoteTreeResponse | null;
  selectedNoteId: string | null;
  search: string;
  onSearchChange: (next: string) => void;
  onSelectNoteId: (noteId: string) => void;
  onCreateNote: () => void;
  isLoading?: boolean;
};

type TreeNode = NoteTreeResponse["items"][number];

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
  selectedNoteId,
  onSelectNoteId,
}: {
  nodes: TreeNode[];
  depth: number;
  selectedNoteId: string | null;
  onSelectNoteId: (noteId: string) => void;
}) {
  return (
    <ul className="space-y-0.5">
      {nodes.map((node) => {
        const isSelected = selectedNoteId === node.note.id;
        const icon = node.note.icon?.trim() || "📄";

        return (
          <li key={node.note.id}>
            <button
              type="button"
              className={cn(
                "hover:bg-accent flex w-full items-center gap-2 truncate rounded-md px-2 py-1 text-left text-sm",
                isSelected && "bg-accent text-accent-foreground",
              )}
              style={{ paddingLeft: `${8 + depth * 12}px` }}
              onClick={() => onSelectNoteId(node.note.id)}
            >
              <span className="text-sm" aria-hidden="true">
                {icon}
              </span>
              <span className="truncate">{node.note.title || "Untitled"}</span>
            </button>

            {node.children.length ? (
              <div className="pt-0.5">
                <TreeList
                  nodes={node.children}
                  depth={depth + 1}
                  selectedNoteId={selectedNoteId}
                  onSelectNoteId={onSelectNoteId}
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
  isLoading,
}: NotesSidebarProps) {
  const nodes = useMemo(() => tree?.items ?? [], [tree]);
  const filtered = useMemo(() => filterTree(nodes, search), [nodes, search]);

  return (
    <aside className="bg-muted/20 flex h-full min-h-0 flex-col border-r">
      <header className="flex items-center justify-between gap-2 p-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">
            {workspace ? `${workspace.icon ?? "📓"} ${workspace.name}` : "Notes"}
          </p>
          <p className="text-muted-foreground truncate text-xs">Markdown-first pages</p>
        </div>
        <Button type="button" size="icon" variant="outline" onClick={onCreateNote}>
          <FilePlus2 className="h-4 w-4" aria-hidden="true" />
          <span className="sr-only">New note</span>
        </Button>
      </header>

      <div className="px-3 pb-3">
        <div className="relative">
          <Search className="text-muted-foreground absolute top-2.5 left-2 h-4 w-4" aria-hidden="true" />
          <Input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search notes…"
            className="pl-8"
          />
        </div>
      </div>

      <Separator />

      <div className="flex-1 overflow-y-auto p-3">
        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-7 w-11/12" />
            <Skeleton className="h-7 w-9/12" />
            <Skeleton className="h-7 w-10/12" />
            <Skeleton className="h-7 w-8/12" />
          </div>
        ) : filtered.length ? (
          <TreeList
            nodes={filtered}
            depth={0}
            selectedNoteId={selectedNoteId}
            onSelectNoteId={onSelectNoteId}
          />
        ) : (
          <EmptyState
            title={nodes.length ? "No matches" : "No notes yet"}
            description={nodes.length ? "Try a different search." : "Create your first note to start dogfooding."}
            action={
              <Button type="button" onClick={onCreateNote}>
                New note
              </Button>
            }
          />
        )}
      </div>
    </aside>
  );
}
