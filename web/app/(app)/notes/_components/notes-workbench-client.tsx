"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import dynamic from "next/dynamic";
import { FilePlus2, PanelLeftOpen, Upload } from "lucide-react";

import { useLocalStorageBoolean, useLocalStorageNumber } from "@/lib/hooks/use-local-storage-value";
import type { NoteTreeNode, Workspace } from "@/lib/api/types/notes";

import { Button } from "@/components/ui/button";
import { ResizableColumns } from "@/components/ui/resizable-columns";
import { useCreateNote, useCreateWorkspace, useDeleteNote } from "@/features/notes/mutations";
import { useNoteTree, useWorkspaces } from "@/features/notes/queries";

import { NotesFilesystemImportDialog } from "./notes-filesystem-import-dialog";
import { NotesSidebar } from "./notes-sidebar";

const NoteEditorPanel = dynamic(
  () => import("./note-editor-panel").then((mod) => ({ default: mod.NoteEditorPanel })),
  {
    ssr: false,
    loading: () => (
      <div className="text-muted-foreground flex h-full items-center justify-center">
        Loading editor...
      </div>
    ),
  },
);

/** Flatten tree into an ordered list of note IDs (depth-first). */
function flattenTree(nodes: NoteTreeNode[]): string[] {
  const ids: string[] = [];
  for (const node of nodes) {
    ids.push(node.note.id);
    ids.push(...flattenTree(node.children));
  }
  return ids;
}

/** Given the current tree and a deleted note ID, find the best next note to select. */
function findNextNoteId(items: NoteTreeNode[], deletedId: string): string | null {
  const flat = flattenTree(items);
  const idx = flat.indexOf(deletedId);
  if (idx === -1) return flat[0] ?? null;
  // Prefer next sibling, then previous, then first available
  return flat[idx + 1] ?? flat[idx - 1] ?? null;
}

function pickDefaultWorkspace(workspaces: Workspace[]): Workspace | null {
  if (!workspaces.length) return null;
  const byDefaultSetting = workspaces.find(
    (w) => (w.settings as Record<string, unknown>)?.default === true,
  );
  if (byDefaultSetting) return byDefaultSetting;
  const personal = workspaces.find((w) => w.name.trim().toLowerCase() === "personal");
  if (personal) return personal;
  return workspaces[0];
}

export function NotesWorkbenchClient({ initialNoteId }: { initialNoteId: string | null }) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [treeSearch, setTreeSearch] = useState("");
  const [leftWidthPx, setLeftWidthPx] = useLocalStorageNumber("alfred:notes:left-width:v1", 340);
  const [sidebarCollapsed, setSidebarCollapsed] = useLocalStorageBoolean(
    "alfred:notes:sidebar-collapsed:v1",
    false,
  );
  const [importDialogOpen, setImportDialogOpen] = useState(false);

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

  // Track the note to navigate to after a delete completes
  const postDeleteTargetRef = useRef<string | null>(null);

  const deleteNoteMutation = useDeleteNote({
    workspaceId,
    onSuccess: () => {
      toast.success("Note deleted");
      const target = postDeleteTargetRef.current;
      postDeleteTargetRef.current = null;
      if (target) {
        router.replace(`/notes?note=${encodeURIComponent(target)}`);
      } else {
        router.replace("/notes");
      }
    },
  });

  const selectedNoteId = searchParams.get("note") || initialNoteId || null;

  // Auto-select first note when the tree loads and nothing is selected
  useEffect(() => {
    if (!selectedNoteId && treeQuery.data?.items?.length) {
      const firstId = flattenTree(treeQuery.data.items)[0];
      if (firstId) {
        router.replace(`/notes?note=${encodeURIComponent(firstId)}`);
      }
    }
  }, [selectedNoteId, treeQuery.data, router]);

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

  const collapseSidebar = () => {
    setSidebarCollapsed(true);
  };

  const expandSidebar = () => {
    setSidebarCollapsed(false);
  };

  const editor = (
    <NoteEditorPanel
      noteId={selectedNoteId}
      workspaceId={workspaceId}
      onCreateNote={onCreateNote}
    />
  );

  return (
    <div className="h-full w-full">
      {sidebarCollapsed ? (
        <div className="flex h-full min-h-0 w-full">
          <aside className="bg-card flex h-full w-14 shrink-0 flex-col items-center gap-2 border-r px-2 py-3">
            <Button type="button" size="icon-sm" variant="ghost" onClick={expandSidebar}>
              <PanelLeftOpen className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only">Expand notes sidebar</span>
            </Button>
            <Button type="button" size="icon-sm" variant="outline" onClick={onCreateNote}>
              <FilePlus2 className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only">New note</span>
            </Button>
            <Button
              type="button"
              size="icon-sm"
              variant="outline"
              onClick={() => setImportDialogOpen(true)}
            >
              <Upload className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only">Import files</span>
            </Button>
            <div className="bg-border mt-2 h-px w-full" />
            <div className="mt-1 text-[10px] font-medium tracking-[0.18em] text-[var(--alfred-text-tertiary)] uppercase [writing-mode:vertical-rl]">
              Notes
            </div>
          </aside>
          <div className="min-h-0 flex-1">{editor}</div>
        </div>
      ) : (
        <ResizableColumns
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
              onImportMarkdown={() => setImportDialogOpen(true)}
              onCollapse={collapseSidebar}
              onSelectNoteId={onSelectNoteId}
              onDeleteNote={(noteId) => {
                // Compute next note BEFORE the tree is invalidated
                const items = treeQuery.data?.items ?? [];
                postDeleteTargetRef.current = findNextNoteId(items, noteId);
                deleteNoteMutation.mutate(noteId);
              }}
            />
          }
          right={editor}
        />
      )}
      <NotesFilesystemImportDialog
        open={importDialogOpen}
        onOpenChange={setImportDialogOpen}
        workspaceId={workspaceId}
        onImported={(noteId) => {
          router.push(`/notes?note=${encodeURIComponent(noteId)}`);
        }}
      />
    </div>
  );
}
