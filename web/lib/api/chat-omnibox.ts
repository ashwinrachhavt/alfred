import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

export type OmniboxResult =
  | {
      kind: "zettel";
      id: number;
      title: string;
      topic: string | null;
      tags: string[];
      source_url?: string | null;
      excerpt?: string | null;
      score?: number;
      query?: string;
    }
  | {
      kind: "document";
      id: string;
      title: string;
      topic: string | null;
      tags?: string[];
      source_url?: string | null;
      excerpt?: string | null;
      score?: number;
      query?: string;
    }
  | {
      kind: "action";
      id: string;
      title: string;
      description: string;
      action: "search_all" | "create_card";
      query: string;
      score?: number;
    };

export type ChatOmniboxResponse = {
  results: OmniboxResult[];
};

export async function searchChatOmnibox(
  query: string | null,
  limit = 8,
): Promise<ChatOmniboxResponse> {
  const params = new URLSearchParams();
  const trimmed = query?.trim() ?? "";
  if (trimmed) params.set("q", trimmed);
  params.set("limit", String(limit));
  return apiFetch<ChatOmniboxResponse>(`${apiRoutes.chat.omnibox}?${params}`, {
    cache: "no-store",
  });
}
