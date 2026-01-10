import { apiFetch, apiPostJson } from "@/lib/api/client";

import type {
  AdminBatchEnqueueResponse,
  DocumentConceptsBacklogResponse,
  DocumentConceptsBatchEnqueueRequest,
  LearningConceptsBacklogResponse,
  LearningConceptsBatchEnqueueRequest,
} from "@/lib/api/types/admin";

type BacklogParams = {
  limit?: number;
  topic_id?: number | null;
  min_age_hours?: number;
};

function buildBacklogQuery(params: BacklogParams): string {
  const query = new URLSearchParams();
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (typeof params.topic_id === "number") query.set("topic_id", String(params.topic_id));
  if (typeof params.min_age_hours === "number") query.set("min_age_hours", String(params.min_age_hours));
  return query.toString();
}

export async function getLearningConceptsBacklog(
  params: BacklogParams,
): Promise<LearningConceptsBacklogResponse> {
  const query = buildBacklogQuery(params);
  return apiFetch<LearningConceptsBacklogResponse>(
    `/api/admin/learning/concepts/backlog${query ? `?${query}` : ""}`,
    { cache: "no-store" },
  );
}

export async function enqueueLearningConceptsBatch(
  body: LearningConceptsBatchEnqueueRequest,
): Promise<AdminBatchEnqueueResponse> {
  return apiPostJson<AdminBatchEnqueueResponse, LearningConceptsBatchEnqueueRequest>(
    "/api/admin/learning/concepts/extract/batch/async",
    body,
    { cache: "no-store" },
  );
}

export async function getDocumentConceptsBacklog(
  params: Omit<BacklogParams, "topic_id">,
): Promise<DocumentConceptsBacklogResponse> {
  const query = buildBacklogQuery(params);
  return apiFetch<DocumentConceptsBacklogResponse>(
    `/api/admin/documents/concepts/backlog${query ? `?${query}` : ""}`,
    { cache: "no-store" },
  );
}

export async function enqueueDocumentConceptsBatch(
  body: DocumentConceptsBatchEnqueueRequest,
): Promise<AdminBatchEnqueueResponse> {
  return apiPostJson<AdminBatchEnqueueResponse, DocumentConceptsBatchEnqueueRequest>(
    "/api/admin/documents/concepts/extract/batch/async",
    body,
    { cache: "no-store" },
  );
}

