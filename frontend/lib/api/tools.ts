import { apiFetch, apiPostJson } from "@/lib/api/client";

import type {
  SlackSendRequest,
  SlackSendResponse,
  StoreQueryRequest,
  StoreQueryResponse,
  ToolsStatusResponse,
} from "@/lib/api/types/tools";

export async function toolsStatus(): Promise<ToolsStatusResponse> {
  return apiFetch<ToolsStatusResponse>("/api/tools/status", { cache: "no-store" });
}

export async function storeQuery(body: StoreQueryRequest): Promise<StoreQueryResponse> {
  return apiPostJson<StoreQueryResponse, StoreQueryRequest>("/api/tools/store/query", body, {
    cache: "no-store",
  });
}

export async function slackSend(body: SlackSendRequest): Promise<SlackSendResponse> {
  return apiPostJson<SlackSendResponse, SlackSendRequest>("/api/tools/slack/send", body, {
    cache: "no-store",
  });
}

