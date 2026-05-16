"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronRight, Plus } from "lucide-react";

import type { NoteResponse } from "@/lib/api/types/notes";

import { cn } from "@/lib/utils";
import { findAncestorIds, type TreeNode } from "@/lib/notes/tree-utils";
import { useNoteTree, useWorkspaces } from "@/features/notes/queries";
import { useCreateChildNote } from "@/features/notes/mutations";

const COLLAPSED_KEY = "alfred:sidebarNotesCollapsedBranches";
const MAX_INDENT_DEPTH = 6;

function pickWorkspaceId(workspaces: { id: string; name: string }[] | undefined): string | null {
  if (!workspaces || workspaces.length === 0) return null;
  const personal = workspaces.find((w) => w.name.trim().toLowerCase() === "personal");
  return (personal ?? workspaces[0]).id;
}

function loadCollapsed(): Record<string, boolean> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(COLLAPSED_KEY);
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

function saveCollapsed(state: Record<string, boolean>): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(COLLAPSED_KEY, JSON.stringify(state));
  } catch {
    // localStorage can throw in private mode — silently degrade
  }
}

type SidebarNotesTreeProps = {
  isOpen: boolean;
  selectedNoteId: string | null;
};

export function SidebarNotesTree({ isOpen, selectedNoteId }: SidebarNotesTreeProps) {
  const router = useRouter();
  const workspacesQuery = useWorkspaces();
  const workspaceId = isOpen ? pickWorkspaceId(workspacesQuery.data) : null;
  const treeQuery = useNoteTree(workspaceId);
  const createChild = useCreateChildNote(workspaceId);

  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(() => loadCollapsed());

  const nodes = useMemo<TreeNode[]>(() => treeQuery.data?.items ?? [], [treeQuery.data]);

  const ancestorSet = useMemo(() => {
    if (!selectedNoteId) return new Set<string>();
    const chain = findAncestorIds(nodes, selectedNoteId) ?? [];
    return new Set(chain);
  }, [nodes, selectedNoteId]);

  if (!isOpen) return null;

  if (workspacesQuery.data && workspacesQuery.data.length === 0) {
    return (
      <p className="px-7 py-1.5 text-[11px] text-[var(--alfred-text-tertiary)]">
        Open Notes to get started
      </p>
    );
  }

  if (treeQuery.isError) {
    return (
      <p className="px-7 py-1.5 text-[11px] text-[var(--alfred-text-tertiary)]">
        Couldn&apos;t load notes
      </p>
    );
  }

  if (!nodes.length) return null;

  const toggleBranch = (noteId: string) => {
    setCollapsed((prev) => {
      const next = { ...prev };
      // Tristate semantics: missing = default-collapsed, false = explicitly expanded,
      // true = explicitly collapsed. Toggling flips between explicit expanded/collapsed
      // so the user's last action is persisted across sessions.
      next[noteId] = prev[noteId] === false;
      saveCollapsed(next);
      return next;
    });
  };

  const handleAddChild = (parentId: string) => {
    createChild.mutate(parentId, {
      onSuccess: (created: NoteResponse) => {
        router.push(`/notes?note=${created.id}`);
      },
    });
  };

  return (
    <ul className="space-y-0.5">
      <TreeRows
        nodes={nodes}
        depth={0}
        collapsed={collapsed}
        ancestorSet={ancestorSet}
        selectedNoteId={selectedNoteId}
        onToggleBranch={toggleBranch}
        onAddChild={handleAddChild}
      />
    </ul>
  );
}

type TreeRowsProps = {
  nodes: TreeNode[];
  depth: number;
  collapsed: Record<string, boolean>;
  ancestorSet: Set<string>;
  selectedNoteId: string | null;
  onToggleBranch: (noteId: string) => void;
  onAddChild: (parentId: string) => void;
};

function TreeRows({
  nodes,
  depth,
  collapsed,
  ancestorSet,
  selectedNoteId,
  onToggleBranch,
  onAddChild,
}: TreeRowsProps) {
  const indentPx = Math.min(depth, MAX_INDENT_DEPTH) * 8;

  return (
    <>
      {nodes.map((node) => {
        const isBranch = node.children.length > 0;
        const isSelected = selectedNoteId === node.note.id;
        const isExpanded =
          isBranch && (ancestorSet.has(node.note.id) || collapsed[node.note.id] === false);
        const icon = node.note.icon?.trim() || (isBranch ? "📁" : "📄");
        const title = node.note.title || "Untitled";

        return (
          <li key={node.note.id} className="group/note relative">
            <div className="flex items-center" style={{ paddingLeft: `${indentPx + 20}px` }}>
              {isBranch ? (
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground -ml-5 shrink-0 rounded p-0.5 transition-colors"
                  onClick={() => onToggleBranch(node.note.id)}
                  aria-label={`${isExpanded ? "Collapse" : "Expand"} ${title}`}
                >
                  {isExpanded ? (
                    <ChevronDown className="size-3" aria-hidden="true" />
                  ) : (
                    <ChevronRight className="size-3" aria-hidden="true" />
                  )}
                </button>
              ) : (
                <span className="-ml-5 size-4 shrink-0" aria-hidden="true" />
              )}

              <a
                href={`/notes?note=${node.note.id}`}
                className={cn(
                  "flex min-w-0 flex-1 items-center gap-1.5 truncate border-l-2 px-2 py-1 text-xs transition-colors",
                  isSelected
                    ? "border-primary bg-[var(--alfred-accent-subtle)] text-primary"
                    : "text-muted-foreground hover:text-foreground border-transparent hover:bg-[var(--alfred-accent-subtle)]",
                )}
              >
                <span aria-hidden="true">{icon}</span>
                <span className="truncate">{title}</span>
              </a>

              <button
                type="button"
                className="text-muted-foreground/0 group-hover/note:text-muted-foreground/60 hover:!text-primary mr-1 shrink-0 rounded p-0.5 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  onAddChild(node.note.id);
                }}
                aria-label={`Add sub-note to ${title}`}
              >
                <Plus className="size-3" aria-hidden="true" />
              </button>
            </div>

            {isBranch && isExpanded ? (
              <TreeRows
                nodes={node.children}
                depth={depth + 1}
                collapsed={collapsed}
                ancestorSet={ancestorSet}
                selectedNoteId={selectedNoteId}
                onToggleBranch={onToggleBranch}
                onAddChild={onAddChild}
              />
            ) : null}
          </li>
        );
      })}
    </>
  );
}
