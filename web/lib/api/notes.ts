import { apiFetch, apiPatchJson, apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import type {
  NoteAssetResponse,
  NoteCreateRequest,
  NoteResponse,
  NoteTreeResponse,
  NoteUpdateRequest,
  Workspace,
  WorkspaceCreateRequest,
} from "@/lib/api/types/notes";

function buildQuery(params: Record<string, string | number | null | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    query.set(key, String(value));
  }
  return query.toString();
}

export async function listWorkspaces(params: { userId?: number | null } = {}): Promise<Workspace[]> {
  const query = buildQuery({ user_id: params.userId });
  const url = query ? `${apiRoutes.notes.workspaces}?${query}` : apiRoutes.notes.workspaces;
  return apiFetch<Workspace[]>(url);
}

export async function createWorkspace(
  payload: WorkspaceCreateRequest,
  params: { userId?: number | null } = {},
): Promise<Workspace> {
  const query = buildQuery({ user_id: params.userId });
  const url = query ? `${apiRoutes.notes.createWorkspace}?${query}` : apiRoutes.notes.createWorkspace;
  return apiPostJson<Workspace, WorkspaceCreateRequest>(
    url,
    payload,
  );
}

export async function getNoteTree(workspaceId: string): Promise<NoteTreeResponse> {
  const query = buildQuery({ workspace_id: workspaceId });
  const url = query ? `${apiRoutes.notes.tree}?${query}` : apiRoutes.notes.tree;
  return apiFetch<NoteTreeResponse>(url);
}

export async function createNote(payload: NoteCreateRequest): Promise<NoteResponse> {
  return apiPostJson<NoteResponse, NoteCreateRequest>(apiRoutes.notes.createNote, payload);
}

export async function getNote(noteId: string): Promise<NoteResponse> {
  return apiFetch<NoteResponse>(apiRoutes.notes.noteById(noteId));
}

export async function updateNote(noteId: string, payload: NoteUpdateRequest): Promise<NoteResponse> {
  return apiPatchJson<NoteResponse, NoteUpdateRequest>(apiRoutes.notes.noteById(noteId), payload);
}

export async function deleteNote(noteId: string): Promise<void> {
  await apiFetch(apiRoutes.notes.noteById(noteId), { method: "DELETE" });
}

export async function uploadNoteAsset(noteId: string, file: File): Promise<NoteAssetResponse> {
  const form = new FormData();
  form.append("file", file, file.name);

  return apiFetch<NoteAssetResponse>(apiRoutes.notes.noteAssets(noteId), {
    method: "POST",
    body: form,
  });
}
