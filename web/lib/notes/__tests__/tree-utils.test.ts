import { describe, expect, it } from "vitest";

import type { NoteSummary, NoteTreeResponse } from "@/lib/api/types/notes";
import { filterTree, findAncestorIds } from "@/lib/notes/tree-utils";

type TreeNode = NoteTreeResponse["items"][number];

function makeNote(id: string, title: string, parentId: string | null = null): NoteSummary {
  return {
    id,
    title,
    icon: null,
    cover_image: null,
    parent_id: parentId,
    workspace_id: "workspace-1",
    position: 0,
    is_archived: false,
    created_at: "2026-05-13T00:00:00Z",
    updated_at: "2026-05-13T00:00:00Z",
  };
}

function leaf(id: string, title: string, parentId: string | null = null): TreeNode {
  return { note: makeNote(id, title, parentId), children: [] };
}

describe("findAncestorIds", () => {
  const tree: TreeNode[] = [
    {
      note: makeNote("a", "A"),
      children: [
        leaf("a1", "A1", "a"),
        {
          note: makeNote("a2", "A2", "a"),
          children: [leaf("a2a", "A2A", "a2")],
        },
      ],
    },
    leaf("b", "B"),
  ];

  it("returns [] when target is a root", () => {
    expect(findAncestorIds(tree, "a")).toEqual([]);
  });

  it("returns the chain of ancestor ids for a nested node", () => {
    expect(findAncestorIds(tree, "a2a")).toEqual(["a", "a2"]);
  });

  it("returns null when target is not present", () => {
    expect(findAncestorIds(tree, "missing")).toBeNull();
  });
});

describe("filterTree", () => {
  const tree: TreeNode[] = [
    {
      note: makeNote("a", "Alpha"),
      children: [leaf("a1", "Apple", "a"), leaf("a2", "Banana", "a")],
    },
    leaf("b", "Cherry"),
  ];

  it("returns the full tree when query is empty", () => {
    expect(filterTree(tree, "")).toEqual(tree);
  });

  it("keeps a parent whose descendant matches the query", () => {
    const result = filterTree(tree, "apple");
    expect(result).toHaveLength(1);
    expect(result[0].note.id).toBe("a");
    expect(result[0].children).toHaveLength(1);
    expect(result[0].children[0].note.id).toBe("a1");
  });

  it("drops branches with no matches", () => {
    const result = filterTree(tree, "nothing-matches");
    expect(result).toEqual([]);
  });

  it("matches case-insensitively on title", () => {
    expect(filterTree(tree, "CHERRY").map((n) => n.note.id)).toEqual(["b"]);
  });
});