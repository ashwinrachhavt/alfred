import { useQuery } from "@tanstack/react-query";

import {
  getEntry,
  listEntries,
  lookupWord,
  searchDictionary,
  type SaveIntent,
} from "@/lib/api/dictionary";

export function useDictionaryLookup(word: string | null) {
  return useQuery({
    queryKey: ["dictionary", "lookup", word],
    queryFn: () => lookupWord(word!),
    enabled: !!word && word.length > 0,
    staleTime: 5 * 60 * 1000,
  });
}

export function useVocabularyEntries(filters?: {
  save_intent?: SaveIntent;
  domain?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ["dictionary", "entries", filters ?? null],
    queryFn: () => listEntries(filters),
    staleTime: 10_000,
  });
}

export function useVocabularyEntry(id: number | null) {
  return useQuery({
    queryKey: ["dictionary", "entry", id],
    queryFn: () => getEntry(id!),
    enabled: id !== null,
    staleTime: 30_000,
  });
}

export function useDictionarySearch(query: string | null) {
  return useQuery({
    queryKey: ["dictionary", "search", query],
    queryFn: () => searchDictionary(query!),
    enabled: !!query && query.length >= 2,
    staleTime: 30_000,
  });
}
