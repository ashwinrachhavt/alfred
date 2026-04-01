"use client";

import { useMemo, useState } from "react";
import { FilePlus2, Search, Trash2 } from "lucide-react";

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
 onDeleteNote?: (noteId: string) => void;
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
 onRequestDelete,
}: {
 nodes: TreeNode[];
 depth: number;
 selectedNoteId: string | null;
 onSelectNoteId: (noteId: string) => void;
 onRequestDelete?: (noteId: string, title: string) => void;
}) {
 return (
 <ul className="space-y-0.5">
 {nodes.map((node) => {
 const isSelected = selectedNoteId === node.note.id;
 const icon = node.note.icon?.trim() || "📄";

 return (
 <li key={node.note.id} className="group/note relative">
 <div className="flex items-center">
 <button
 type="button"
 className={cn(
 "flex flex-1 items-center gap-2 truncate rounded-md px-2 py-1.5 text-left text-sm transition-colors",
 isSelected
 ? "border-l-2 border-primary bg-[var(--alfred-accent-subtle)] text-foreground"
 : "border-l-2 border-transparent text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
 )}
 style={{ paddingLeft:`${8 + depth * 12}px` }}
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
 className="shrink-0 p-1 rounded transition-colors mr-1 text-muted-foreground/0 group-hover/note:text-muted-foreground/60 hover:!text-[var(--error)]"
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

 {node.children.length ? (
 <div className="pt-0.5">
 <TreeList
 nodes={node.children}
 depth={depth + 1}
 selectedNoteId={selectedNoteId}
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
 onDeleteNote,
 isLoading,
}: NotesSidebarProps) {
 const nodes = useMemo(() => tree?.items ?? [], [tree]);
 const filtered = useMemo(() => filterTree(nodes, search), [nodes, search]);

 const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null);

 const handleConfirmDelete = () => {
 if (deleteTarget && onDeleteNote) {
 onDeleteNote(deleteTarget.id);
 }
 setDeleteTarget(null);
 };

 return (
 <aside className="flex h-full min-h-0 flex-col border-r bg-card">
 <header className="flex items-center justify-between gap-2 border-b p-3">
 <div className="min-w-0">
 <p className="truncate text-lg">
 {workspace ?`${workspace.icon ?? "📓"} ${workspace.name}` : "Notes"}
 </p>
 <p className="truncate font-medium text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Markdown-first pages
 </p>
 </div>
 <Button type="button" size="icon" variant="outline" onClick={onCreateNote}>
 <FilePlus2 className="h-4 w-4" aria-hidden="true" />
 <span className="sr-only">New note</span>
 </Button>
 </header>

 <div className="px-3 py-3">
 <div className="relative">
 <Search className="absolute top-2.5 left-2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
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
 selectedNoteId={selectedNoteId}
 onSelectNoteId={onSelectNoteId}
 onRequestDelete={
 onDeleteNote
 ? (id, title) => setDeleteTarget({ id, title })
 : undefined
 }
 />
 ) : (
 <EmptyState
 title={nodes.length ? "No matches" : "No notes yet"}
 description={nodes.length ? "Try a different search." : "Create your first note to get started."}
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
 Are you sure you want to delete &ldquo;{deleteTarget?.title}&rdquo;? This action cannot be undone.
 </DialogDescription>
 </DialogHeader>
 <DialogFooter className="gap-2 sm:gap-0">
 <Button variant="ghost" onClick={() => setDeleteTarget(null)}>
 Cancel
 </Button>
 <Button
 variant="destructive"
 onClick={handleConfirmDelete}
 className="text-xs"
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
