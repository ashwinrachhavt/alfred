"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import dynamic from "next/dynamic";

import { safeGetItem } from "@/lib/storage";
import type { NoteTreeNode, Workspace } from "@/lib/api/types/notes";

import { ResizableColumns } from "@/components/ui/resizable-columns";
import { useCreateNote, useCreateWorkspace, useDeleteNote } from "@/features/notes/mutations";
import { useNoteTree, useWorkspaces } from "@/features/notes/queries";

import { NotesSidebar } from "./notes-sidebar";

const NoteEditorPanel = dynamic(() => import("./note-editor-panel").then((mod) => ({ default: mod.NoteEditorPanel })), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-muted-foreground">
      Loading editor...
    </div>
  ),
});

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
 onDeleteNote={(noteId) => {
 // Compute next note BEFORE the tree is invalidated
 const items = treeQuery.data?.items ?? [];
 postDeleteTargetRef.current = findNextNoteId(items, noteId);
 deleteNoteMutation.mutate(noteId);
 }}
 />
 }
 right={<NoteEditorPanel noteId={selectedNoteId} workspaceId={workspaceId} onCreateNote={onCreateNote} />}
 />
 </div>
 );
}
