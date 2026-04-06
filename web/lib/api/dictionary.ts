import { apiFetch, apiPostJson, apiPatchJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

// --------------- Types ---------------

export type DefinitionSense = {
  definition: string;
  examples: string[];
};

export type DefinitionGroup = {
  part_of_speech: string;
  senses: DefinitionSense[];
};

export type DictionaryResult = {
  word: string;
  pronunciation_ipa: string | null;
  pronunciation_audio_url: string | null;
  definitions: DefinitionGroup[];
  etymology: string | null;
  synonyms: { sense: string; words: string[] }[] | null;
  antonyms: { sense: string; words: string[] }[] | null;
  usage_notes: string | null;
  wikipedia_summary: string | null;
  ai_explanation: string | null;
  source_urls: string[];
};

export type SaveIntent = "learning" | "reference" | "encountered";

export type VocabularyEntry = {
  id: number;
  word: string;
  language: string;
  pronunciation_ipa: string | null;
  pronunciation_audio_url: string | null;
  definitions: DefinitionGroup[] | null;
  etymology: string | null;
  synonyms: { sense: string; words: string[] }[] | null;
  antonyms: { sense: string; words: string[] }[] | null;
  usage_notes: string | null;
  wikipedia_summary: string | null;
  ai_explanation: string | null;
  ai_explanation_domains: string[] | null;
  source_urls: string[] | null;
  personal_notes: string | null;
  domain_tags: string[] | null;
  save_intent: SaveIntent;
  bloom_level: number;
  zettel_id: number | null;
  created_at: string;
  updated_at: string;
};

export type VocabularyListItem = {
  id: number;
  word: string;
  language: string;
  pronunciation_ipa: string | null;
  definitions: DefinitionGroup[] | null;
  domain_tags: string[] | null;
  save_intent: SaveIntent;
  bloom_level: number;
  created_at: string;
  updated_at: string;
};

export type SaveEntryPayload = {
  word: string;
  language?: string;
  pronunciation_ipa?: string | null;
  pronunciation_audio_url?: string | null;
  definitions?: DefinitionGroup[] | null;
  etymology?: string | null;
  synonyms?: { sense: string; words: string[] }[] | null;
  antonyms?: { sense: string; words: string[] }[] | null;
  usage_notes?: string | null;
  wikipedia_summary?: string | null;
  ai_explanation?: string | null;
  ai_explanation_domains?: string[] | null;
  source_urls?: string[] | null;
  personal_notes?: string | null;
  domain_tags?: string[] | null;
  save_intent: SaveIntent;
  bloom_level?: number;
};

export type UpdateEntryPayload = {
  personal_notes?: string;
  domain_tags?: string[];
  bloom_level?: number;
  save_intent?: SaveIntent;
};

export type SearchResult = {
  query: string;
  saved: {
    id: number;
    word: string;
    save_intent: SaveIntent;
    domain_tags: string[] | null;
  }[];
  lookup: DictionaryResult;
};

// --------------- API calls ---------------

export function lookupWord(word: string): Promise<DictionaryResult> {
  return apiFetch<DictionaryResult>(
    `${apiRoutes.dictionary.lookup}?word=${encodeURIComponent(word)}`,
    { cache: "no-store" },
  );
}

export function saveEntry(
  payload: SaveEntryPayload,
): Promise<{ id: number; word: string }> {
  return apiPostJson(apiRoutes.dictionary.entries, payload);
}

export function listEntries(params?: {
  save_intent?: SaveIntent;
  domain?: string;
  limit?: number;
  offset?: number;
}): Promise<VocabularyListItem[]> {
  const searchParams = new URLSearchParams();
  if (params?.save_intent) searchParams.set("save_intent", params.save_intent);
  if (params?.domain) searchParams.set("domain", params.domain);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const qs = searchParams.toString();
  const url = qs
    ? `${apiRoutes.dictionary.entries}?${qs}`
    : apiRoutes.dictionary.entries;
  return apiFetch<VocabularyListItem[]>(url, { cache: "no-store" });
}

export function getEntry(id: number): Promise<VocabularyEntry> {
  return apiFetch<VocabularyEntry>(apiRoutes.dictionary.entryById(id), {
    cache: "no-store",
  });
}

export function updateEntry(
  id: number,
  payload: UpdateEntryPayload,
): Promise<{ id: number; word: string }> {
  return apiPatchJson(apiRoutes.dictionary.entryById(id), payload);
}

export function deleteEntry(id: number): Promise<{ deleted: boolean }> {
  return apiFetch<{ deleted: boolean }>(apiRoutes.dictionary.entryById(id), {
    method: "DELETE",
  });
}

export function searchDictionary(query: string): Promise<SearchResult> {
  return apiFetch<SearchResult>(
    `${apiRoutes.dictionary.search}?q=${encodeURIComponent(query)}`,
    { cache: "no-store" },
  );
}

export function regenerateAiExplanation(
  id: number,
): Promise<{ id: number; ai_explanation: string }> {
  return apiPostJson(apiRoutes.dictionary.regenerateAi(id), {});
}
