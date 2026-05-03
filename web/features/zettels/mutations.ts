import { useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  bulkCreateZettelCards,
  createZettelCard,
  createZettelLink,
  createZettelStream,
  deleteZettelCard,
  deleteZettelLink,
  generateZettelCard,
  previewGeneratedZettelCard,
  updateZettelCard,
  updateZettelLink,
} from "@/lib/api/zettels";
import type {
  AIGeneratePayload,
  ApiZettelCard,
  ZettelCardCreatePayload,
  ZettelCardUpdatePayload,
  ZettelLinkCreatePayload,
  ZettelLinkUpdatePayload,
} from "@/lib/api/zettels";
import { useZettelCreationStore } from "@/lib/stores/zettel-creation-store";

const ZETTEL_CARDS_KEY = ["zettels", "cards"];
const ZETTEL_COUNT_KEY = ["zettels", "count"];
const ZETTEL_GRAPH_KEY = ["zettels", "graph"];
const ZETTEL_TOPICS_KEY = ["zettel-topics"];
const ZETTEL_TAGS_KEY = ["zettel-tags"];

function zettelCardKey(cardId: number) {
  return ["zettels", "card", cardId] as const;
}
function zettelLinksKey(cardId: number) {
  return ["zettels", "links", cardId] as const;
}
function zettelBacklinksKey(cardId: number) {
  return ["zettels", "backlinks", cardId] as const;
}

export function useCreateZettel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ZettelCardCreatePayload) => createZettelCard(payload),
    onMutate: async (newCard) => {
      await queryClient.cancelQueries({ queryKey: ZETTEL_CARDS_KEY });
      const previous = queryClient.getQueryData<ApiZettelCard[]>(ZETTEL_CARDS_KEY);
      queryClient.setQueryData<ApiZettelCard[]>(ZETTEL_CARDS_KEY, (old) => {
        const optimistic: ApiZettelCard = {
          id: -Date.now(),
          title: newCard.title,
          content: newCard.content ?? null,
          summary: newCard.summary ?? null,
          tags: newCard.tags ?? null,
          topic: newCard.topic ?? null,
          source_url: newCard.source_url ?? null,
          document_id: null,
          importance: newCard.importance ?? 0,
          confidence: newCard.confidence ?? 0,
          status: "active",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        return [optimistic, ...(old || [])];
      });
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(ZETTEL_CARDS_KEY, context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ZETTEL_CARDS_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_COUNT_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_GRAPH_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_TOPICS_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_TAGS_KEY });
    },
  });
}

export function useBulkCreateZettels() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ZettelCardCreatePayload[]) => bulkCreateZettelCards(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ZETTEL_CARDS_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_COUNT_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_GRAPH_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_TOPICS_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_TAGS_KEY });
    },
  });
}

export function useUpdateZettel(cardId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ZettelCardUpdatePayload) => updateZettelCard(cardId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: zettelCardKey(cardId) });
      queryClient.invalidateQueries({ queryKey: ZETTEL_CARDS_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_TOPICS_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_TAGS_KEY });
    },
  });
}

export function useDeleteZettel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cardId: number) => deleteZettelCard(cardId),
    onSuccess: (_data, cardId) => {
      queryClient.invalidateQueries({ queryKey: ZETTEL_CARDS_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_COUNT_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_GRAPH_KEY });
      queryClient.removeQueries({ queryKey: zettelCardKey(cardId) });
      queryClient.removeQueries({ queryKey: zettelLinksKey(cardId) });
      queryClient.removeQueries({ queryKey: zettelBacklinksKey(cardId) });
    },
  });
}

export function useCreateZettelLink(cardId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ZettelLinkCreatePayload) => createZettelLink(cardId, payload),
    onSuccess: (_data, payload) => {
      queryClient.invalidateQueries({ queryKey: zettelLinksKey(cardId) });
      queryClient.invalidateQueries({ queryKey: zettelBacklinksKey(payload.to_card_id) });
      queryClient.invalidateQueries({ queryKey: ZETTEL_GRAPH_KEY });
    },
  });
}

export function useDeleteZettelLink() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (linkId: number) => deleteZettelLink(linkId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["zettels", "links"] });
      queryClient.invalidateQueries({ queryKey: ["zettels", "backlinks"] });
      queryClient.invalidateQueries({ queryKey: ZETTEL_GRAPH_KEY });
    },
  });
}

export function useUpdateZettelLink() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (args: { linkId: number; payload: ZettelLinkUpdatePayload }) =>
      updateZettelLink(args.linkId, args.payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["zettels", "links"] });
      queryClient.invalidateQueries({ queryKey: ZETTEL_GRAPH_KEY });
    },
  });
}

export function useGenerateZettel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AIGeneratePayload) => generateZettelCard(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ZETTEL_CARDS_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_COUNT_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_GRAPH_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_TOPICS_KEY });
      queryClient.invalidateQueries({ queryKey: ZETTEL_TAGS_KEY });
    },
  });
}

export function usePreviewGeneratedZettel() {
  return useMutation({
    mutationFn: (payload: AIGeneratePayload) => previewGeneratedZettelCard(payload),
  });
}

/**
 * Start a streaming zettel creation. Connects SSE and
 * feeds events to the Zustand store.
 */
export function useCreateZettelStream() {
  const store = useZettelCreationStore();

  const startStream = useCallback(
    async (payload: ZettelCardCreatePayload, signal?: AbortSignal) => {
      store.startStream();
      try {
        await createZettelStream(payload, store.handleEvent, signal);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          store.handleEvent("error", {
            step: "connection",
            message: (err as Error).message,
          });
        }
      }
    },
    [store],
  );

  return { startStream };
}
