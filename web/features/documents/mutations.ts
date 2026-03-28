import { useMutation, useQueryClient } from "@tanstack/react-query";

import { enrichDocument, fetchAndOrganize, updateDocumentText, type UpdateDocumentTextRequest } from "@/lib/api/documents";
import { documentDetailsQueryKey } from "@/features/documents/queries";

export function useUpdateDocumentText(docId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: UpdateDocumentTextRequest) => updateDocumentText(docId, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(documentDetailsQueryKey(docId), updated);
    },
  });
}

export function useFetchAndOrganize(docId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (force?: boolean) => fetchAndOrganize(docId, force),
    onSuccess: () => {
      // Poll for enrichment completion
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: documentDetailsQueryKey(docId) });
        queryClient.invalidateQueries({ queryKey: ["documents", "explorer"] });
      }, 8000);
    },
  });
}

export function useEnrichDocument(docId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (force?: boolean) => enrichDocument(docId, force),
    onSuccess: () => {
      // Invalidate after a delay to give Celery time to process
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: documentDetailsQueryKey(docId) });
        queryClient.invalidateQueries({ queryKey: ["documents", "explorer"] });
      }, 5000);
    },
  });
}
