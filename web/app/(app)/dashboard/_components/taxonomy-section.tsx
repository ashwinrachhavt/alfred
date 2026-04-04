"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { ChevronRight, RefreshCw, FolderTree, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import {
 useTaxonomyTree,
 useReclassifyAll,
 useCreateTaxonomyNode,
 useUpdateTaxonomyNode,
 useDeleteTaxonomyNode,
} from "@/features/taxonomy/queries";
import type { TaxonomyTreeNode } from "@/lib/api/types/taxonomy";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
 Dialog,
 DialogContent,
 DialogDescription,
 DialogFooter,
 DialogHeader,
 DialogTitle,
 DialogTrigger,
 DialogClose,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

/* ---------- Inline editable name ---------- */

function InlineEdit({
 value,
 onSave,
 className,
}: {
 value: string;
 onSave: (newValue: string) => void;
 className?: string;
}) {
 const [editing, setEditing] = useState(false);
 const [draft, setDraft] = useState(value);
 const inputRef = useRef<HTMLInputElement>(null);

 useEffect(() => {
 if (editing) {
 inputRef.current?.focus();
 inputRef.current?.select();
 }
 }, [editing]);

 const commit = useCallback(() => {
 const trimmed = draft.trim();
 if (trimmed && trimmed !== value) {
 onSave(trimmed);
 }
 setEditing(false);
 }, [draft, value, onSave]);

 if (editing) {
 return (
 <input
 ref={inputRef}
 value={draft}
 onChange={(e) => setDraft(e.target.value)}
 onBlur={commit}
 onKeyDown={(e) => {
 if (e.key === "Enter") commit();
 if (e.key === "Escape") {
 setDraft(value);
 setEditing(false);
 }
 }}
 className="bg-secondary border border-border rounded-sm px-1.5 py-0.5 text-sm outline-none focus:ring-1 focus:ring-[#E8590C]/50"
 />
 );
 }

 return (
 <span
 onDoubleClick={() => {
 setDraft(value);
 setEditing(true);
 }}
 className={cn("cursor-default select-none", className)}
 title="Double-click to rename"
 >
 {value}
 </span>
 );
}

/* ---------- Delete confirmation dialog ---------- */

function DeleteNodeDialog({
 node,
 onConfirm,
 isPending,
}: {
 node: TaxonomyTreeNode;
 onConfirm: () => void;
 isPending: boolean;
}) {
 const [open, setOpen] = useState(false);
 const hasChildren = node.children.length > 0;

 return (
 <Dialog open={open} onOpenChange={setOpen}>
 <DialogTrigger asChild>
 <button
 type="button"
 className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded-sm hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
 title="Delete node"
 >
 <Trash2 className="size-3" />
 </button>
 </DialogTrigger>
 <DialogContent>
 <DialogHeader>
 <DialogTitle className="">
 Delete &ldquo;{node.display_name}&rdquo;
 </DialogTitle>
 <DialogDescription>
 {hasChildren ? (
 <>
 This node has{" "}
 <strong className="text-foreground">
 {node.children.length} child{node.children.length > 1 ? "ren" : ""}
 </strong>
 . Deleting it will also remove all descendants.
 </>
 ) : (
 "This will permanently remove this taxonomy node."
 )}
 </DialogDescription>
 </DialogHeader>
 <DialogFooter>
 <DialogClose asChild>
 <Button variant="ghost" className="text-xs">
 Cancel
 </Button>
 </DialogClose>
 <Button
 variant="destructive"
 className="text-xs gap-1.5"
 disabled={isPending}
 onClick={() => {
 onConfirm();
 setOpen(false);
 }}
 >
 {isPending ? "Deleting..." : "Delete"}
 </Button>
 </DialogFooter>
 </DialogContent>
 </Dialog>
 );
}

/* ---------- Add child inline form ---------- */

function AddChildForm({
 parentSlug,
 parentLevel,
 onCreated,
}: {
 parentSlug: string | null;
 parentLevel: number;
 onCreated: () => void;
}) {
 const [name, setName] = useState("");
 const inputRef = useRef<HTMLInputElement>(null);
 const createMutation = useCreateTaxonomyNode();

 useEffect(() => {
 inputRef.current?.focus();
 }, []);

 const submit = useCallback(() => {
 const trimmed = name.trim();
 if (!trimmed) {
 onCreated();
 return;
 }
 createMutation.mutate(
 {
 name: trimmed,
 level: parentLevel + 1,
 parent_slug: parentSlug,
 },
 { onSettled: () => onCreated() },
 );
 }, [name, parentSlug, parentLevel, createMutation, onCreated]);

 return (
 <input
 ref={inputRef}
 value={name}
 placeholder={
 parentLevel === 0
 ? "New domain..."
 : parentLevel === 1
 ? "New topic..."
 : "New subtopic..."
 }
 onChange={(e) => setName(e.target.value)}
 onBlur={submit}
 onKeyDown={(e) => {
 if (e.key === "Enter") submit();
 if (e.key === "Escape") onCreated();
 }}
 className="bg-secondary border border-border rounded-sm px-1.5 py-0.5 text-sm outline-none focus:ring-1 focus:ring-[#E8590C]/50 w-48"
 />
 );
}

/* ---------- Reclassify prompt after edits ---------- */

function ReclassifyPrompt({ onDismiss }: { onDismiss: () => void }) {
 const { mutate, isPending } = useReclassifyAll();

 return (
 <div className="flex items-center gap-3 rounded-md border border-[#E8590C]/30 bg-[var(--alfred-accent-subtle)] px-3 py-2">
 <span className="text-xs text-foreground">
 Taxonomy changed. Reclassify zettels?
 </span>
 <div className="flex gap-1.5 ml-auto">
 <Button
 size="sm"
 variant="ghost"
 className="text-xs h-6 px-2"
 onClick={onDismiss}
 >
 Dismiss
 </Button>
 <Button
 size="sm"
 className="text-xs h-6 px-2 bg-[#E8590C] text-white hover:bg-[#E8590C]/90 gap-1"
 disabled={isPending}
 onClick={() =>
 mutate(undefined, { onSettled: () => onDismiss() })
 }
 >
 {isPending && <RefreshCw className="size-3 animate-spin" />}
 {isPending ? "Classifying..." : "Reclassify"}
 </Button>
 </div>
 </div>
 );
}

/* ---------- Tree node (recursive, editable) ---------- */

function TreeNode({
 node,
 depth = 0,
 onTaxonomyChanged,
}: {
 node: TaxonomyTreeNode;
 depth?: number;
 onTaxonomyChanged: () => void;
}) {
 const [expanded, setExpanded] = useState(depth === 0);
 const [addingChild, setAddingChild] = useState(false);
 const hasChildren = node.children.length > 0;
 // Use tree depth (not stored level) to determine if children are allowed,
 // since the classifier sometimes assigns wrong levels (e.g., level 3 under level 1)
 const canAddChild = depth < 2; // depth 0 = domain, depth 1 = subdomain, depth 2 = leaf

 const updateMutation = useUpdateTaxonomyNode();
 const deleteMutation = useDeleteTaxonomyNode();

 const handleRename = useCallback(
 (newName: string) => {
 updateMutation.mutate(
 { slug: node.slug, payload: { name: newName } },
 { onSuccess: () => onTaxonomyChanged() },
 );
 },
 [node.slug, updateMutation, onTaxonomyChanged],
 );

 const handleDelete = useCallback(() => {
 deleteMutation.mutate(
 { slug: node.slug },
 { onSuccess: () => onTaxonomyChanged() },
 );
 }, [node.slug, deleteMutation, onTaxonomyChanged]);

 return (
 <div>
 <div
 className="group flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm transition-colors hover:bg-[var(--alfred-accent-subtle)]"
 style={{ paddingLeft:`${depth * 20 + 8}px` }}
 >
 {/* Expand chevron */}
 <button
 type="button"
 onClick={() => (hasChildren || addingChild) && setExpanded((prev) => !prev)}
 className={cn(
 "shrink-0",
 hasChildren || addingChild ? "cursor-pointer" : "cursor-default",
 )}
 >
 {hasChildren || addingChild ? (
 <ChevronRight
 className={cn(
 "size-3.5 text-muted-foreground transition-transform duration-150",
 expanded && "rotate-90",
 )}
 />
 ) : (
 <span className="size-3.5" />
 )}
 </button>

 {/* Editable display name */}
 <InlineEdit
 value={node.display_name}
 onSave={handleRename}
 className={cn(depth === 0 ? "text-base font-medium" : "text-sm text-foreground")}
 />

 {/* Doc count badge */}
 <span className="ml-auto text-[10px] tabular-nums text-muted-foreground">
 {node.doc_count}
 </span>

 {/* Add child button (hover) */}
 {canAddChild && (
 <button
 type="button"
 onClick={() => {
 setAddingChild(true);
 setExpanded(true);
 }}
 className="opacity-30 group-hover:opacity-100 transition-opacity p-0.5 rounded-sm hover:bg-[var(--alfred-accent-subtle)] text-muted-foreground hover:text-[#E8590C]"
 title="Add child"
 >
 <Plus className="size-3" />
 </button>
 )}

 {/* Delete button (hover) */}
 <DeleteNodeDialog
 node={node}
 onConfirm={handleDelete}
 isPending={deleteMutation.isPending}
 />
 </div>

 {/* Children */}
 {expanded && (
 <div>
 {node.children.map((child) => (
 <TreeNode
 key={child.slug}
 node={child}
 depth={depth + 1}
 onTaxonomyChanged={onTaxonomyChanged}
 />
 ))}
 {addingChild && (
 <div style={{ paddingLeft:`${(depth + 1) * 20 + 8 + 22}px` }} className="py-1">
 <AddChildForm
 parentSlug={node.slug}
 parentLevel={node.level}
 onCreated={() => {
 setAddingChild(false);
 onTaxonomyChanged();
 }}
 />
 </div>
 )}
 </div>
 )}
 </div>
 );
}

/* ---------- Reclassify button with confirmation ---------- */

function ReclassifyButton() {
 const { mutate, isPending } = useReclassifyAll();
 const [open, setOpen] = useState(false);
 const [mounted, setMounted] = useState(false);
 useEffect(() => setMounted(true), []);

 const handleConfirm = useCallback(() => {
 setOpen(false);
 mutate(undefined, {
 onSuccess: () => {
 toast.success("Reclassification started in background. This may take a few minutes.");
 },
 onError: () => {
 toast.error("Failed to start reclassification.");
 },
 });
 }, [mutate]);

 if (!mounted) {
 return (
 <Button size="sm" variant="ghost" className="text-xs gap-1.5">
 <RefreshCw className="size-3" />
 Reclassify All
 </Button>
 );
 }

 return (
 <Dialog open={open} onOpenChange={setOpen}>
 <DialogTrigger asChild>
 <Button size="sm" variant="ghost" className="text-xs gap-1.5">
 <RefreshCw className="size-3" />
 Reclassify All
 </Button>
 </DialogTrigger>
 <DialogContent>
 <DialogHeader>
 <DialogTitle>Reclassify All Zettels</DialogTitle>
 <DialogDescription>
 This will re-run the taxonomy classifier on every document in the background.
 You can continue working while it runs.
 </DialogDescription>
 </DialogHeader>
 <DialogFooter>
 <DialogClose asChild>
 <Button variant="ghost" className="text-xs">
 Cancel
 </Button>
 </DialogClose>
 <Button
 onClick={handleConfirm}
 disabled={isPending}
 className="text-xs gap-1.5 bg-[#E8590C] text-white hover:bg-[#E8590C]/90"
 >
 <RefreshCw className="size-3" />
 Start Reclassification
 </Button>
 </DialogFooter>
 </DialogContent>
 </Dialog>
 );
}

/* ---------- Main section ---------- */

export function TaxonomySection() {
 const { data: tree, isLoading, isError } = useTaxonomyTree();
 const [showReclassifyPrompt, setShowReclassifyPrompt] = useState(false);
 const [addingDomain, setAddingDomain] = useState(false);

 const totalDomains = tree?.length ?? 0;
 const totalDocs = tree?.reduce((sum, d) => sum + d.doc_count, 0) ?? 0;

 const handleTaxonomyChanged = useCallback(() => {
 setShowReclassifyPrompt(true);
 }, []);

 return (
 <Card>
 <CardContent className="pt-5 space-y-4">
 {/* Header row */}
 <div className="flex items-center justify-between">
 <div className="flex items-center gap-2">
 <FolderTree className="size-4 text-[#E8590C]" />
 <span className="font-medium text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Taxonomy
 </span>
 </div>
 <div className="flex items-center gap-1">
 <Button
 size="sm"
 variant="ghost"
 className="text-xs gap-1.5"
 onClick={() => setAddingDomain(true)}
 >
 <Plus className="size-3" />
 Add Domain
 </Button>
 <ReclassifyButton />
 </div>
 </div>

 {/* Reclassify prompt after edits */}
 {showReclassifyPrompt && (
 <ReclassifyPrompt onDismiss={() => setShowReclassifyPrompt(false)} />
 )}

 {isLoading ? (
 <Skeleton className="h-40 w-full" />
 ) : isError ? (
 <p className="text-sm text-muted-foreground">Failed to load taxonomy tree.</p>
 ) : totalDomains === 0 && !addingDomain ? (
 <p className="text-sm text-muted-foreground">
 No taxonomy data yet. Ingest some documents and run reclassification.
 </p>
 ) : (
 <>
 {/* Summary stats */}
 <div className="flex gap-6">
 <div>
 <div className="font-data text-3xl font-semibold tabular-nums">{totalDomains}</div>
 <div className="text-[10px] text-muted-foreground">domains</div>
 </div>
 <div>
 <div className="font-data text-3xl font-semibold tabular-nums">{totalDocs}</div>
 <div className="text-[10px] text-muted-foreground">classified</div>
 </div>
 </div>

 {/* Tree */}
 <div className="max-h-80 overflow-y-auto rounded-md border bg-background p-1">
 {(tree ?? []).map((domain) => (
 <TreeNode
 key={domain.slug}
 node={domain}
 depth={0}
 onTaxonomyChanged={handleTaxonomyChanged}
 />
 ))}
 {addingDomain && (
 <div className="px-2 py-1">
 <AddChildForm
 parentSlug={null}
 parentLevel={0}
 onCreated={() => {
 setAddingDomain(false);
 handleTaxonomyChanged();
 }}
 />
 </div>
 )}
 </div>
 </>
 )}
 </CardContent>
 </Card>
 );
}
