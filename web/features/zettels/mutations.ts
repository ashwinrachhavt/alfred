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
  updateZettelCard,
} from "@/lib/api/zettels";
import type {
  AIGeneratePayload,
  ApiZettelCard,
  ZettelCardCreatePayload,
  ZettelCardUpdatePayload,
  ZettelLinkCreatePayload,
} from "@/lib/api/zettels";
import { useZettelCreationStore } from "@/lib/stores/zettel-creation-store";

const ZETTEL_CARDS_KEY = ["zettels", "cards"];
const ZETTELS_KEY = ["zettels"];

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
      queryClient.invalidateQueries({ queryKey: ZETTELS_KEY });
    },
  });
}

export function useBulkCreateZettels() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ZettelCardCreatePayload[]) => bulkCreateZettelCards(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ZETTELS_KEY });
    },
  });
}

export function useUpdateZettel(cardId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ZettelCardUpdatePayload) => updateZettelCard(cardId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ZETTELS_KEY });
    },
  });
}

export function useDeleteZettel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cardId: number) => deleteZettelCard(cardId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ZETTELS_KEY });
    },
  });
}

export function useCreateZettelLink(cardId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ZettelLinkCreatePayload) => createZettelLink(cardId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ZETTELS_KEY });
    },
  });
}

export function useDeleteZettelLink() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (linkId: number) => deleteZettelLink(linkId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ZETTELS_KEY });
    },
  });
}

export function useGenerateZettel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AIGeneratePayload) => generateZettelCard(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ZETTELS_KEY });
    },
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
