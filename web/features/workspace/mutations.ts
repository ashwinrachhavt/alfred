import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  bulkFromDecomposition,
  createSession,
  endSession,
  resumeEnrichment,
  type BulkFromDecompositionBody,
  type BulkFromDecompositionResult,
  type CreateSessionBody,
  type ResumeEnrichmentResult,
  type ZettelSessionOut,
} from "@/lib/api/workspace";

export function useCreateSession() {
  const qc = useQueryClient();
  return useMutation<ZettelSessionOut, Error, CreateSessionBody | undefined>({
    mutationFn: (body) => createSession(body ?? {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workspace"] });
    },
  });
}

export function useEndSession() {
  const qc = useQueryClient();
  return useMutation<ZettelSessionOut, Error, number>({
    mutationFn: (id) => endSession(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ["workspace", "session", id] });
      qc.invalidateQueries({ queryKey: ["zettels"] });
    },
  });
}

export function useResumeEnrichment(sessionId: number | null) {
  const qc = useQueryClient();
  return useMutation<ResumeEnrichmentResult, Error, number>({
    mutationFn: (cardId) => resumeEnrichment(cardId),
    onSuccess: (_data, cardId) => {
      qc.invalidateQueries({ queryKey: ["zettels", "card", cardId] });
      if (sessionId !== null) {
        qc.invalidateQueries({
          queryKey: ["workspace", "session", sessionId],
        });
      }
    },
  });
}

export function useBulkFromDecomposition() {
  const qc = useQueryClient();
  return useMutation<
    BulkFromDecompositionResult,
    Error,
    BulkFromDecompositionBody
  >({
    mutationFn: (body) => bulkFromDecomposition(body),
    onSuccess: (_data, body) => {
      if (body.session_id) {
        qc.invalidateQueries({
          queryKey: ["workspace", "session", body.session_id],
        });
      }
      qc.invalidateQueries({ queryKey: ["zettels"] });
    },
  });
}
