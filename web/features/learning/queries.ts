import { useQuery } from "@tanstack/react-query";

import { getDailyDeck } from "@/lib/api/learning";

export const DAILY_DECK_KEY = ["learning", "daily-deck"];

export function useDailyDeck(limit = 20) {
  return useQuery({
    queryKey: [...DAILY_DECK_KEY, limit],
    queryFn: () => getDailyDeck(limit),
    staleTime: 5 * 60_000, // 5 min — deck doesn't change during a session
  });
}
