import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import {
  listZettelCards as apiListZettelCards,
  countZettelCards as apiCountZettelCards,
  listZettelLinks,
  listZettelsByDocument,
  listZettelTopics,
  listZettelTags,
  type ZettelFilterParams,
} from "@/lib/api/zettels";
import type { Zettel, BloomLevel } from "@/app/(app)/knowledge/_components/mock-data";

type ApiZettelCard = {
  id: number;
  title: string;
  content: string | null;
  summary: string | null;
  tags: string[] | null;
  topic: string | null;
  source_url: string | null;
  document_id: string | null;
  importance: number;
  confidence: number;
  status: string;
  created_at: string;
  updated_at: string;
};

type GraphEdge = { from: number; to: number; type: string };
type GraphSummary = { nodes: unknown[]; edges: GraphEdge[] };

function buildConnectionMap(edges: GraphEdge[]): Map<string, string[]> {
  const map = new Map<string, string[]>();

  function addEdge(a: string, b: string) {
    if (!map.has(a)) map.set(a, []);
    if (!map.get(a)!.includes(b)) map.get(a)!.push(b);
  }

  for (const edge of edges) {
    const fromKey = String(edge.from);
    const toKey = String(edge.to);
    // Bidirectional: both ends see the connection
    addEdge(fromKey, toKey);
    addEdge(toKey, fromKey);
  }
  return map;
}

function mapApiToZettel(card: ApiZettelCard, connections: string[]): Zettel {
  return {
    id: String(card.id),
    title: card.title,
    content: card.content || "",
    summary: card.content || card.summary || "",
    tags: card.tags || [],
    connections,
    status: card.status,
    bloomLevel: Math.max(1, Math.min(6, Math.round(card.confidence * 6))) as BloomLevel,
    bloomHistory: [],
    source: {
      title: card.title,
      url: card.source_url || undefined,
      capturedAt: card.created_at,
    },
    lastReviewedAt: null,
    nextReviewAt: null,
    quizHistory: { attempts: 0, correct: 0 },
    quizQuestions: [],
    feynmanGaps: [],
    createdAt: card.created_at,
    updatedAt: card.updated_at,
  };
}

export function useZettelCards(filters?: ZettelFilterParams) {
  return useQuery({
    queryKey: ["zettels", "cards", filters || null],
    queryFn: async () => {
      // When no status filter is set, fetch all non-archived cards (active + draft)
      const effectiveFilters = {
        ...filters,
        status: filters?.status || undefined, // undefined = no status filter sent to API
      };
      const [cards, graph] = await Promise.all([
        apiListZettelCards(effectiveFilters),
        apiFetch<GraphSummary>(apiRoutes.zettels.graph, { cache: "no-store" }),
      ]);

      const connectionMap = buildConnectionMap(graph.edges);
      return cards
        .filter((c) => c.status !== "archived")
        .map((c) => mapApiToZettel(c, connectionMap.get(String(c.id)) || []));
    },
    staleTime: 10_000,
  });
}

export function useZettelCount(filters?: ZettelFilterParams) {
  return useQuery({
    queryKey: ["zettels", "count", filters || null],
    queryFn: () => apiCountZettelCards(filters),
    staleTime: 10_000,
  });
}

export function useZettelTopics() {
  return useQuery({
    queryKey: ["zettel-topics"],
    queryFn: () => listZettelTopics(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useZettelTags() {
  return useQuery({
    queryKey: ["zettel-tags"],
    queryFn: () => listZettelTags(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useZettelLinks(cardId: number | null) {
  return useQuery({
    queryKey: ["zettels", "links", cardId],
    queryFn: () => listZettelLinks(cardId!),
    enabled: cardId !== null,
    staleTime: 10_000,
  });
}

export function useZettelsByDocument(documentId: string | null) {
  return useQuery({
    queryKey: ["zettels", "by-document", documentId],
    queryFn: () => listZettelsByDocument(documentId!),
    enabled: documentId !== null,
    staleTime: 10_000,
  });
}

export function useZettelReviewsDue() {
  return useQuery({
    queryKey: ["zettels", "reviews", "due"],
    queryFn: () => apiFetch<Array<{ id: number; card_id: number }>>(apiRoutes.zettels.reviewsDue, { cache: "no-store" }),
    staleTime: 30_000,
  });
}
