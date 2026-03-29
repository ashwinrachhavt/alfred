"use client";

import { useState, useCallback } from "react";
import { ChevronRight, RefreshCw, FolderTree } from "lucide-react";

import { useTaxonomyTree, useReclassifyAll } from "@/features/taxonomy/queries";
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

/* ---------- Tree node (recursive) ---------- */

function TreeNode({ node, depth = 0 }: { node: TaxonomyTreeNode; depth?: number }) {
  const [expanded, setExpanded] = useState(depth === 0);
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <button
        type="button"
        onClick={() => hasChildren && setExpanded((prev) => !prev)}
        className={cn(
          "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm transition-colors hover:bg-[var(--alfred-accent-subtle)]",
          hasChildren && "cursor-pointer",
          !hasChildren && "cursor-default",
        )}
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
      >
        {/* Expand chevron */}
        {hasChildren ? (
          <ChevronRight
            className={cn(
              "size-3.5 shrink-0 text-muted-foreground transition-transform duration-150",
              expanded && "rotate-90",
            )}
          />
        ) : (
          <span className="size-3.5 shrink-0" />
        )}

        {/* Display name */}
        <span className={cn(depth === 0 ? "font-serif text-base" : "text-sm text-foreground")}>
          {node.display_name}
        </span>

        {/* Doc count badge */}
        <span className="ml-auto font-mono text-[10px] tabular-nums text-muted-foreground">
          {node.doc_count}
        </span>
      </button>

      {/* Children */}
      {expanded && hasChildren && (
        <div>
          {node.children.map((child) => (
            <TreeNode key={child.slug} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- Reclassify button with confirmation ---------- */

function ReclassifyButton() {
  const { mutate, isPending, data, isSuccess } = useReclassifyAll();
  const [open, setOpen] = useState(false);

  const handleConfirm = useCallback(() => {
    mutate(undefined, {
      onSettled: () => setOpen(false),
    });
  }, [mutate]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="ghost" className="font-mono text-xs gap-1.5">
          <RefreshCw className="size-3" />
          Reclassify All
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-serif">Reclassify All Zettels</DialogTitle>
          <DialogDescription>
            This will re-run the taxonomy classifier on every document. It may take a while depending
            on the size of your knowledge base.
          </DialogDescription>
        </DialogHeader>
        {isSuccess && data && (
          <div className="rounded-md border bg-card p-3 font-mono text-xs space-y-1">
            <div>Total: {data.total ?? 0}</div>
            <div>Classified: {data.classified ?? 0}</div>
            <div>Failed: {data.failed ?? 0}</div>
            <div>Skipped: {data.skipped ?? 0}</div>
          </div>
        )}
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="ghost" className="font-mono text-xs">
              Cancel
            </Button>
          </DialogClose>
          <Button
            onClick={handleConfirm}
            disabled={isPending}
            className="font-mono text-xs gap-1.5 bg-[#E8590C] text-white hover:bg-[#E8590C]/90"
          >
            {isPending && <RefreshCw className="size-3 animate-spin" />}
            {isPending ? "Classifying..." : "Confirm"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ---------- Main section ---------- */

export function TaxonomySection() {
  const { data: tree, isLoading, isError } = useTaxonomyTree();

  const totalDomains = tree?.length ?? 0;
  const totalDocs = tree?.reduce((sum, d) => sum + d.doc_count, 0) ?? 0;

  return (
    <Card>
      <CardContent className="pt-5 space-y-4">
        {/* Header row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FolderTree className="size-4 text-[#E8590C]" />
            <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
              Taxonomy
            </span>
          </div>
          <ReclassifyButton />
        </div>

        {isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : isError ? (
          <p className="text-sm text-muted-foreground">Failed to load taxonomy tree.</p>
        ) : totalDomains === 0 ? (
          <p className="text-sm text-muted-foreground">
            No taxonomy data yet. Ingest some documents and run reclassification.
          </p>
        ) : (
          <>
            {/* Summary stats */}
            <div className="flex gap-6">
              <div>
                <div className="font-data text-3xl font-semibold tabular-nums">{totalDomains}</div>
                <div className="font-mono text-[10px] text-muted-foreground">domains</div>
              </div>
              <div>
                <div className="font-data text-3xl font-semibold tabular-nums">{totalDocs}</div>
                <div className="font-mono text-[10px] text-muted-foreground">classified</div>
              </div>
            </div>

            {/* Tree */}
            <div className="max-h-80 overflow-y-auto rounded-md border bg-background p-1">
              {(tree ?? []).map((domain) => (
                <TreeNode key={domain.slug} node={domain} depth={0} />
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
