import type { NoteTreeResponse } from "@/lib/api/types/notes";

export type TreeNode = NoteTreeResponse["items"][number];

export function findAncestorIds(nodes: TreeNode[], targetId: string): string[] | null {
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

export function filterTree(nodes: TreeNode[], query: string): TreeNode[] {
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