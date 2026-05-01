import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { NoteSummary, NoteTreeResponse } from "@/lib/api/types/notes";

import { NotesSidebar } from "../notes-sidebar";

function makeNote(id: string, title: string, overrides: Partial<NoteSummary> = {}): NoteSummary {
  return {
    id,
    title,
    icon: null,
    cover_image: null,
    parent_id: null,
    workspace_id: "workspace-1",
    position: 0,
    is_archived: false,
    created_at: "2026-04-12T00:00:00Z",
    updated_at: "2026-04-12T00:00:00Z",
    ...overrides,
  };
}

const tree: NoteTreeResponse = {
  workspace_id: "workspace-1",
  items: [
    {
      note: makeNote("folder-1", "Claude"),
      children: [
        {
          note: makeNote("file-1", "Memory.md", { parent_id: "folder-1" }),
          children: [],
        },
      ],
    },
  ],
};

function renderSidebar(selectedNoteId: string | null = null) {
  return render(
    <NotesSidebar
      workspace={null}
      tree={tree}
      selectedNoteId={selectedNoteId}
      search=""
      onSearchChange={vi.fn()}
      onSelectNoteId={vi.fn()}
      onCreateNote={vi.fn()}
      onImportMarkdown={vi.fn()}
      onCollapse={vi.fn()}
    />,
  );
}

describe("NotesSidebar", () => {
  it("collapses and expands folder branches", () => {
    renderSidebar();

    expect(screen.getByRole("button", { name: "Memory.md" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Collapse Claude" }));
    expect(screen.queryByRole("button", { name: "Memory.md" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Expand Claude" }));
    expect(screen.getByRole("button", { name: "Memory.md" })).toBeInTheDocument();
  });

  it("reopens the selected note path after a branch was collapsed", () => {
    const { rerender } = renderSidebar();

    fireEvent.click(screen.getByRole("button", { name: "Collapse Claude" }));
    expect(screen.queryByRole("button", { name: "Memory.md" })).not.toBeInTheDocument();

    rerender(
      <NotesSidebar
        workspace={null}
        tree={tree}
        selectedNoteId="file-1"
        search=""
        onSearchChange={vi.fn()}
        onSelectNoteId={vi.fn()}
        onCreateNote={vi.fn()}
        onImportMarkdown={vi.fn()}
        onCollapse={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Memory.md" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Collapse Claude" })).toBeInTheDocument();
  });
});
