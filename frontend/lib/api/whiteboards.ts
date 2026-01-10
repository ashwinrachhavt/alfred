import { apiFetch, apiPatchJson, apiPostJson } from "@/lib/api/client";

import type {
  WhiteboardCommentCreate,
  WhiteboardCommentOut,
  WhiteboardCreate,
  WhiteboardRevisionCreate,
  WhiteboardRevisionOut,
  WhiteboardUpdate,
  WhiteboardWithRevision,
} from "@/lib/api/types/whiteboards";

export async function listWhiteboards(params?: {
  include_archived?: boolean;
  limit?: number;
  skip?: number;
}): Promise<WhiteboardWithRevision[]> {
  const query = new URLSearchParams();
  if (params?.include_archived) query.set("include_archived", "true");
  if (typeof params?.limit === "number") query.set("limit", String(params.limit));
  if (typeof params?.skip === "number") query.set("skip", String(params.skip));
  const qs = query.toString();
  return apiFetch<WhiteboardWithRevision[]>(`/api/whiteboards${qs ? `?${qs}` : ""}`, {
    cache: "no-store",
  });
}

export async function createWhiteboard(body: WhiteboardCreate): Promise<WhiteboardWithRevision> {
  return apiPostJson<WhiteboardWithRevision, WhiteboardCreate>("/api/whiteboards", body, {
    cache: "no-store",
  });
}

export async function getWhiteboard(boardId: number): Promise<WhiteboardWithRevision> {
  return apiFetch<WhiteboardWithRevision>(`/api/whiteboards/${boardId}`, { cache: "no-store" });
}

export async function updateWhiteboard(
  boardId: number,
  body: WhiteboardUpdate,
): Promise<WhiteboardWithRevision> {
  return apiPatchJson<WhiteboardWithRevision, WhiteboardUpdate>(`/api/whiteboards/${boardId}`, body, {
    cache: "no-store",
  });
}

export async function addWhiteboardRevision(
  boardId: number,
  body: WhiteboardRevisionCreate,
): Promise<WhiteboardRevisionOut> {
  return apiPostJson<WhiteboardRevisionOut, WhiteboardRevisionCreate>(
    `/api/whiteboards/${boardId}/revisions`,
    body,
    { cache: "no-store" },
  );
}

export async function listWhiteboardRevisions(boardId: number): Promise<WhiteboardRevisionOut[]> {
  return apiFetch<WhiteboardRevisionOut[]>(`/api/whiteboards/${boardId}/revisions`, {
    cache: "no-store",
  });
}

export async function addWhiteboardComment(
  boardId: number,
  body: WhiteboardCommentCreate,
): Promise<WhiteboardCommentOut> {
  return apiPostJson<WhiteboardCommentOut, WhiteboardCommentCreate>(
    `/api/whiteboards/${boardId}/comments`,
    body,
    { cache: "no-store" },
  );
}

export async function listWhiteboardComments(boardId: number): Promise<WhiteboardCommentOut[]> {
  return apiFetch<WhiteboardCommentOut[]>(`/api/whiteboards/${boardId}/comments`, {
    cache: "no-store",
  });
}

