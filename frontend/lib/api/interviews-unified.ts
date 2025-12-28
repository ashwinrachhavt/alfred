import { apiFetch, apiPostJson } from "@/lib/api/client";
import type {
  EnqueueUnifiedInterviewTaskResponse,
  UnifiedInterviewRequest,
  UnifiedInterviewResponse,
} from "@/lib/api/types/interviews-unified";

export async function processUnifiedInterview(
  payload: UnifiedInterviewRequest,
  options?: { background?: boolean },
): Promise<UnifiedInterviewResponse | EnqueueUnifiedInterviewTaskResponse> {
  const background = options?.background ? "?background=true" : "";
  return apiPostJson<UnifiedInterviewResponse | EnqueueUnifiedInterviewTaskResponse, UnifiedInterviewRequest>(
    `/api/interviews-unified/process${background}`,
    payload,
    { cache: "no-store" },
  );
}

export async function getTaskStatus<TResponse>(statusUrl: string): Promise<TResponse> {
  return apiFetch<TResponse>(statusUrl, { cache: "no-store" });
}
