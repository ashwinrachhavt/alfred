import { apiFetch, apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import type {
  DocumentDetailsResponse,
  ExplorerDocumentsResponse,
  SemanticMapResponse,
} from "@/lib/api/types/documents";

type ListExplorerDocumentsParams = {
  limit?: number;
  cursor?: string | null;
  filter_topic?: string | null;
  search?: string | null;
};

function buildExplorerDocumentsQuery(params: ListExplorerDocumentsParams): string {
  const query = new URLSearchParams();
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (params.cursor) query.set("cursor", params.cursor);
  if (params.filter_topic) query.set("filter_topic", params.filter_topic);
  if (params.search) query.set("search", params.search);
  return query.toString();
}

export async function listExplorerDocuments(
  params: ListExplorerDocumentsParams = {},
): Promise<ExplorerDocumentsResponse> {
  const query = buildExplorerDocumentsQuery(params);
  const url = query ? `${apiRoutes.documents.explorer}?${query}` : apiRoutes.documents.explorer;
  return apiFetch<ExplorerDocumentsResponse>(url, { cache: "no-store" });
}

type GetSemanticMapParams = {
  limit?: number;
  refresh?: boolean;
};

function buildSemanticMapQuery(params: GetSemanticMapParams): string {
  const query = new URLSearchParams();
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (params.refresh) query.set("refresh", "true");
  return query.toString();
}

export async function getSemanticMap(params: GetSemanticMapParams = {}): Promise<SemanticMapResponse> {
  const query = buildSemanticMapQuery(params);
  const url = query ? `${apiRoutes.documents.semanticMap}?${query}` : apiRoutes.documents.semanticMap;
  return apiFetch<SemanticMapResponse>(url, { cache: "no-store" });
}

export async function getDocumentDetails(id: string): Promise<DocumentDetailsResponse> {
  return apiFetch<DocumentDetailsResponse>(apiRoutes.documents.documentDetails(id), {
    cache: "no-store",
  });
}

export type GenerateDocumentImageRequest = {
  model?: string;
  size?: string;
  quality?: string;
};

export type GenerateDocumentImageResponse = {
  id: string;
  status: string;
  cover_image_url?: string | null;
  skipped?: boolean;
  reason?: string | null;
};

export type EnqueueDocumentImageResponse = {
  id: string;
  status: string;
  task_id?: string | null;
  status_url?: string | null;
};

type EnqueueDocumentImageParams = {
  force?: boolean;
};

function buildForceQuery(params: EnqueueDocumentImageParams): string {
  const query = new URLSearchParams();
  if (params.force) query.set("force", "true");
  return query.toString();
}

export async function generateDocumentImage(
  id: string,
  params: EnqueueDocumentImageParams = {},
  body: GenerateDocumentImageRequest = {},
): Promise<GenerateDocumentImageResponse> {
  const query = buildForceQuery(params);
  const url = query ? `${apiRoutes.documents.documentImage(id)}?${query}` : apiRoutes.documents.documentImage(id);
  return apiPostJson<GenerateDocumentImageResponse, GenerateDocumentImageRequest>(url, body, {
    cache: "no-store",
  });
}

export async function enqueueDocumentImage(
  id: string,
  params: EnqueueDocumentImageParams = {},
  body: GenerateDocumentImageRequest = {},
): Promise<EnqueueDocumentImageResponse> {
  const query = buildForceQuery(params);
  const url = query ? `${apiRoutes.documents.documentImageAsync(id)}?${query}` : apiRoutes.documents.documentImageAsync(id);
  return apiPostJson<EnqueueDocumentImageResponse, GenerateDocumentImageRequest>(url, body, {
    cache: "no-store",
  });
}
