"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { safeGetItem } from "@/lib/storage";
import type { Workspace } from "@/lib/api/types/notes";

import { ResizableColumns } from "@/components/ui/resizable-columns";
import { useCreateNote, useCreateWorkspace, useDeleteNote } from "@/features/notes/mutations";
import { useNoteTree, useWorkspaces } from "@/features/notes/queries";

import { NoteEditorPanel } from "./note-editor-panel";
import { NotesSidebar } from "./notes-sidebar";

function readStoredNumber(key: string, fallback: number): number {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = safeGetItem(key);
    const parsed = raw ? Number(raw) : Number.NaN;
    return Number.isFinite(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function pickDefaultWorkspace(workspaces: Workspace[]): Workspace | null {
  if (!workspaces.length) return null;
  const byDefaultSetting = workspaces.find((w) => (w.settings as Record<string, unknown>)?.default === true);
  if (byDefaultSetting) return byDefaultSetting;
  const personal = workspaces.find((w) => w.name.trim().toLowerCase() === "personal");
  if (personal) return personal;
  return workspaces[0];
}

export function NotesWorkbenchClient({ initialNoteId }: { initialNoteId: string | null }) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [treeSearch, setTreeSearch] = useState("");
  const [leftWidthPx, setLeftWidthPx] = useState(() =>
    readStoredNumber("alfred:notes:left-width:v1", 340),
  );

  const workspacesQuery = useWorkspaces();
  const { mutate: createWorkspaceMutate, isPending: isCreatingWorkspace } = useCreateWorkspace();
  const didEnsureWorkspaceRef = useRef(false);

  const workspaces = useMemo(() => workspacesQuery.data ?? [], [workspacesQuery.data]);
  const activeWorkspace = useMemo(() => pickDefaultWorkspace(workspaces), [workspaces]);
  const workspaceId = activeWorkspace?.id ?? null;

  useEffect(() => {
    if (!workspacesQuery.isSuccess) return;
    if (workspaces.length) return;
    if (isCreatingWorkspace) return;
    if (didEnsureWorkspaceRef.current) return;

    didEnsureWorkspaceRef.current = true;
    createWorkspaceMutate(
      { name: "Personal", icon: "📓", settings: { default: true } },
      {
        onError: (err) => {
          didEnsureWorkspaceRef.current = false;
          toast.error(err instanceof Error ? err.message : "Failed to create workspace.");
        },
      },
    );
  }, [createWorkspaceMutate, isCreatingWorkspace, workspaces.length, workspacesQuery.isSuccess]);

  const treeQuery = useNoteTree(workspaceId);
  const createNote = useCreateNote({ workspaceId });
  const deleteNoteMutation = useDeleteNote({
    workspaceId,
    onSuccess: () => {
      toast.success("Note deleted");
      // If the deleted note was selected, clear selection
      if (selectedNoteId) {
        router.push("/notes");
      }
    },
  });

  const selectedNoteId = searchParams.get("note") || initialNoteId || null;

  const onSelectNoteId = (noteId: string) => {
    router.push(`/notes?note=${encodeURIComponent(noteId)}`);
  };

  const onCreateNote = async () => {
    if (!workspaceId) return;
    try {
      const created = await createNote.mutateAsync({
        workspace_id: workspaceId,
        title: "Untitled",
        content_markdown: "",
      });
      router.push(`/notes?note=${encodeURIComponent(created.id)}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create note.");
    }
  };

  return (
    <div className="h-full w-full">
      <ResizableColumns
        storageKey="alfred:notes:left-width:v1"
        leftWidthPx={leftWidthPx}
        onLeftWidthPxChange={setLeftWidthPx}
        left={
          <NotesSidebar
            workspace={activeWorkspace}
            tree={treeQuery.data ?? null}
            isLoading={workspacesQuery.isPending || treeQuery.isPending || isCreatingWorkspace}
            selectedNoteId={selectedNoteId}
            search={treeSearch}
            onSearchChange={setTreeSearch}
            onCreateNote={onCreateNote}
            onSelectNoteId={onSelectNoteId}
            onDeleteNote={(noteId) => deleteNoteMutation.mutate(noteId)}
          />
        }
        right={<NoteEditorPanel noteId={selectedNoteId} workspaceId={workspaceId} onCreateNote={onCreateNote} />}
      />
    </div>
  );
}
