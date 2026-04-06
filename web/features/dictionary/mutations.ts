import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  deleteEntry,
  regenerateAiExplanation,
  saveEntry,
  updateEntry,
  type SaveEntryPayload,
  type UpdateEntryPayload,
} from "@/lib/api/dictionary";

const ENTRIES_KEY = ["dictionary", "entries"];

export function useSaveEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SaveEntryPayload) => saveEntry(payload),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ENTRIES_KEY });
    },
  });
}

export function useUpdateEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number;
      payload: UpdateEntryPayload;
    }) => updateEntry(id, payload),
    onSettled: (_data, _err, variables) => {
      queryClient.invalidateQueries({ queryKey: ENTRIES_KEY });
      queryClient.invalidateQueries({
        queryKey: ["dictionary", "entry", variables.id],
      });
    },
  });
}

export function useDeleteEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteEntry(id),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ENTRIES_KEY });
    },
  });
}

export function useRegenerateAiExplanation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => regenerateAiExplanation(id),
    onSettled: (_data, _err, id) => {
      queryClient.invalidateQueries({
        queryKey: ["dictionary", "entry", id],
      });
    },
  });
}
