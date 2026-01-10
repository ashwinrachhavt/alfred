import { apiPostJson } from "@/lib/api/client";

import type {
  AgentQueryRequest,
  MindPalaceQueryResponse,
} from "@/lib/api/types/mind-palace";

export type MindPalaceQueryParams = {
  background?: boolean;
};

export async function queryMindPalaceAgent(
  body: AgentQueryRequest,
  params: MindPalaceQueryParams = {},
): Promise<MindPalaceQueryResponse> {
  const query = new URLSearchParams();
  if (params.background) query.set("background", "true");
  const qs = query.toString();
  return apiPostJson<MindPalaceQueryResponse, AgentQueryRequest>(
    `/api/mind-palace/agent/query${qs ? `?${qs}` : ""}`,
    body,
    { cache: "no-store" },
  );
}

