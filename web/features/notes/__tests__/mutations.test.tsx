import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useUpdateNote } from "@/features/notes/mutations";
import { noteTreeQueryKey } from "@/features/notes/queries";
import { updateNote } from "@/lib/api/notes";
import type { NoteResponse } from "@/lib/api/types/notes";

vi.mock("@/lib/api/notes", () => ({
  createNote: vi.fn(),
  createWorkspace: vi.fn(),
  deleteNote: vi.fn(),
  importNoteFilesystem: vi.fn(),
  updateNote: vi.fn(),
  uploadNoteAsset: vi.fn(),
}));

const updatedNote: NoteResponse = {
  id: "note-1",
  title: "Updated",
  icon: null,
  cover_image: null,
  parent_id: null,
  workspace_id: "workspace-1",
  position: 0,
  is_archived: false,
  content_markdown: "Body",
  content_json: { type: "doc", content: [] },
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
  created_by: null,
  last_edited_by: null,
};

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useUpdateNote", () => {
  beforeEach(() => {
    vi.mocked(updateNote).mockReset();
    vi.mocked(updateNote).mockResolvedValue(updatedNote);
  });

  it("does not invalidate the note tree for content-only autosaves", async () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useUpdateNote("note-1", { workspaceId: "workspace-1" }), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({
        content_markdown: "Body",
        content_json: { type: "doc", content: [] },
      });
    });

    expect(invalidateSpy).not.toHaveBeenCalledWith({
      queryKey: noteTreeQueryKey("workspace-1"),
    });
  });

  it("invalidates the note tree when sidebar-visible metadata changes", async () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useUpdateNote("note-1", { workspaceId: "workspace-1" }), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({ title: "Updated" });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: noteTreeQueryKey("workspace-1"),
    });
  });
});
