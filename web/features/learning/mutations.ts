import { useMutation, useQueryClient } from "@tanstack/react-query";

import { completeReview, generateQuizForTopic } from "@/lib/api/learning";
import { DAILY_DECK_KEY } from "./queries";

export function useCompleteReview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ reviewId, score }: { reviewId: number; score: number }) =>
      completeReview(reviewId, score),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DAILY_DECK_KEY });
    },
  });
}

export function useGenerateQuiz() {
  return useMutation({
    mutationFn: ({ topicId, questionCount }: { topicId: number; questionCount?: number }) =>
      generateQuizForTopic(topicId, questionCount),
  });
}
