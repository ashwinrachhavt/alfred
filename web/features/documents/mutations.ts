import { useMutation, useQueryClient } from "@tanstack/react-query";

import { updateDocumentText, type UpdateDocumentTextRequest } from "@/lib/api/documents";
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
