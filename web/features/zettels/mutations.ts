import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createZettelCard,
  createZettelLink,
  deleteZettelCard,
  deleteZettelLink,
  generateZettelCard,
  updateZettelCard,
} from "@/lib/api/zettels";
import type {
  AIGeneratePayload,
  ZettelCardCreatePayload,
  ZettelCardUpdatePayload,
  ZettelLinkCreatePayload,
} from "@/lib/api/zettels";

const ZETTEL_CARDS_KEY = ["zettels", "cards"];
const ZETTEL_LINKS_KEY = (cardId: number) => ["zettels", "links", cardId];

export function useCreateZettel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ZettelCardCreatePayload) => createZettelCard(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ZETTEL_CARDS_KEY });
    },
  });
}

export function useUpdateZettel(cardId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ZettelCardUpdatePayload) => updateZettelCard(cardId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ZETTEL_CARDS_KEY });
    },
  });
}

export function useDeleteZettel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cardId: number) => deleteZettelCard(cardId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ZETTEL_CARDS_KEY });
    },
  });
}

export function useCreateZettelLink(cardId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ZettelLinkCreatePayload) => createZettelLink(cardId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ZETTEL_LINKS_KEY(cardId) });
      queryClient.invalidateQueries({ queryKey: ZETTEL_CARDS_KEY });
    },
  });
}

export function useDeleteZettelLink(cardId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (linkId: number) => deleteZettelLink(linkId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ZETTEL_LINKS_KEY(cardId) });
      queryClient.invalidateQueries({ queryKey: ZETTEL_CARDS_KEY });
    },
  });
}

export function useGenerateZettel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AIGeneratePayload) => generateZettelCard(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ZETTEL_CARDS_KEY });
    },
  });
}
