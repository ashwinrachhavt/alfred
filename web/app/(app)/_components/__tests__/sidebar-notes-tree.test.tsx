import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { NoteSummary, NoteTreeResponse, Workspace } from "@/lib/api/types/notes";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/notes",
  useSearchParams: () => new URLSearchParams(""),
}));

const mockUseWorkspaces = vi.fn();
const mockUseNoteTree = vi.fn();
vi.mock("@/features/notes/queries", async (orig) => {
  const actual = await orig<typeof import("@/features/notes/queries")>();
  return {
    ...actual,
    useWorkspaces: () => mockUseWorkspaces(),
    useNoteTree: (workspaceId: string | null) => mockUseNoteTree(workspaceId),
  };
});

const mockMutate = vi.fn();
vi.mock("@/features/notes/mutations", () => ({
  useCreateChildNote: () => ({ mutate: mockMutate, isPending: false }),
}));

import { SidebarNotesTree } from "../sidebar-notes-tree";

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

const workspace: Workspace = {
  id: "workspace-1",
  name: "Personal",
  icon: "📓",
  user_id: 1,
  settings: {},
  created_at: "2026-05-13T00:00:00Z",
  updated_at: "2026-05-13T00:00:00Z",
};

const tree: NoteTreeResponse = {
  workspace_id: "workspace-1",
  items: [
    {
      note: makeNote("folder-1", "AI Engineering"),
      children: [{ note: makeNote("file-1", "LLMs", "folder-1"), children: [] }],
    },
    { note: makeNote("file-2", "Finance"), children: [] },
  ],
};

function renderTree(props: { isOpen?: boolean; selectedNoteId?: string | null } = {}) {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <SidebarNotesTree
        isOpen={props.isOpen ?? true}
        selectedNoteId={props.selectedNoteId ?? null}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  mockPush.mockReset();
  mockMutate.mockReset();
  mockUseWorkspaces.mockReturnValue({ data: [workspace], isLoading: false });
  mockUseNoteTree.mockReturnValue({ data: tree, isLoading: false, isError: false });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("SidebarNotesTree", () => {
  it("does not call useNoteTree with a workspaceId when closed", () => {
    mockUseWorkspaces.mockReturnValue({ data: [workspace], isLoading: false });
    renderTree({ isOpen: false });
    expect(mockUseNoteTree).toHaveBeenCalledWith(null);
  });

  it("renders top-level notes when open", () => {
    renderTree();
    expect(screen.getByText("AI Engineering")).toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();
  });

  it("hides children of collapsed branches", () => {
    renderTree();
    expect(screen.queryByText("LLMs")).not.toBeInTheDocument();
  });

  it("expands a branch when its chevron is clicked and persists to localStorage", () => {
    renderTree();
    const chevron = screen.getByLabelText(/Expand AI Engineering/i);
    fireEvent.click(chevron);
    expect(screen.getByText("LLMs")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText(/Collapse AI Engineering/i));
    expect(screen.queryByText("LLMs")).not.toBeInTheDocument();
    const stored = JSON.parse(
      localStorage.getItem("alfred:sidebarNotesCollapsedBranches") ?? "{}",
    );
    expect(stored["folder-1"]).toBe(true);
  });

  it("auto-expands the ancestor chain when selectedNoteId is a nested note", () => {
    renderTree({ selectedNoteId: "file-1" });
    expect(screen.getByText("LLMs")).toBeInTheDocument();
  });

  it("creates a child note and routes to /notes?note=<id> on + click", async () => {
    mockMutate.mockImplementation((_parentId, opts) => {
      opts?.onSuccess?.({ id: "new-note-id" });
    });
    renderTree();

    const addButtons = screen.getAllByLabelText(/Add sub-note to/i);
    fireEvent.click(addButtons[0]);

    await waitFor(() => expect(mockMutate).toHaveBeenCalled());
    expect(mockMutate.mock.calls[0][0]).toBe("folder-1");
    expect(mockPush).toHaveBeenCalledWith("/notes?note=new-note-id");
  });

  it("renders a fallback when no workspace exists", () => {
    mockUseWorkspaces.mockReturnValue({ data: [], isLoading: false });
    renderTree();
    expect(screen.getByText(/Open Notes to get started/i)).toBeInTheDocument();
  });

  it("renders nothing when the tree is empty", () => {
    mockUseNoteTree.mockReturnValue({
      data: { workspace_id: "workspace-1", items: [] },
      isLoading: false,
      isError: false,
    });
    const { container } = renderTree();
    expect(container.querySelector("ul")).toBeNull();
  });
});
