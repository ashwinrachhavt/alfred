"use client";

import { useCallback, useState } from "react";
import { BookOpen, Grid } from "lucide-react";

import { DictionaryEntry } from "@/components/dictionary/dictionary-entry";
import { DictionaryEntrySkeleton } from "@/components/dictionary/dictionary-entry-skeleton";
import { DictionarySearchBar } from "@/components/dictionary/dictionary-search-bar";
import { SaveBar } from "@/components/dictionary/save-bar";
import { VocabularyCollection } from "@/components/dictionary/vocabulary-collection";
import { useDictionaryLookup } from "@/features/dictionary/queries";
import { useSaveEntry } from "@/features/dictionary/mutations";
import { useDictionaryStore } from "@/lib/stores/dictionary-store";
import type { SaveIntent } from "@/lib/api/dictionary";

export default function DictionaryPage() {
  const [lookupWord, setLookupWord] = useState<string | null>(null);
  const activeTab = useDictionaryStore((s) => s.activeTab);
  const setActiveTab = useDictionaryStore((s) => s.setActiveTab);

  const { data: result, isLoading } = useDictionaryLookup(lookupWord);
  const saveMutation = useSaveEntry();

  const handleLookup = useCallback(
    (word: string) => {
      setLookupWord(word);
      setActiveTab("search");
    },
    [setActiveTab],
  );

  const handleSave = useCallback(
    (intent: SaveIntent) => {
      if (!result) return;
      saveMutation.mutate({
        word: result.word,
        pronunciation_ipa: result.pronunciation_ipa,
        pronunciation_audio_url: result.pronunciation_audio_url,
        definitions: result.definitions,
        etymology: result.etymology,
        synonyms: result.synonyms,
        antonyms: result.antonyms,
        usage_notes: result.usage_notes,
        wikipedia_summary: result.wikipedia_summary,
        ai_explanation: result.ai_explanation,
        source_urls: result.source_urls,
        save_intent: intent,
      });
    },
    [result, saveMutation],
  );

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] flex-col">
      <div className="flex items-center justify-between border-b px-6 py-4">
        <h2 className="font-serif text-xl font-semibold">Dictionary</h2>
        <div className="flex gap-1">
          <button
            onClick={() => setActiveTab("search")}
            className={`rounded-md p-2 transition-colors ${
              activeTab === "search"
                ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <BookOpen className="h-4 w-4" />
          </button>
          <button
            onClick={() => setActiveTab("collection")}
            className={`rounded-md p-2 transition-colors ${
              activeTab === "collection"
                ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Grid className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="px-6 pt-8 pb-6">
        <DictionarySearchBar onLookup={handleLookup} />
      </div>

      <div className="flex-1 overflow-y-auto px-6">
        {activeTab === "search" ? (
          <>
            {isLoading && <DictionaryEntrySkeleton />}
            {result && !isLoading && (
              <DictionaryEntry result={result} onWordClick={handleLookup} />
            )}
            {!result && !isLoading && !lookupWord && (
              <div className="py-24 text-center">
                <p className="font-serif text-2xl text-muted-foreground/50">
                  Look up any word
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Search to see definitions, etymology, and AI-powered
                  explanations
                </p>
              </div>
            )}
          </>
        ) : (
          <VocabularyCollection onSelect={handleLookup} />
        )}
      </div>

      {activeTab === "search" && result && !saveMutation.isSuccess && (
        <SaveBar onSave={handleSave} isSaving={saveMutation.isPending} />
      )}

      {saveMutation.isSuccess && (
        <div className="sticky bottom-0 z-10 border-t bg-background/95 px-4 py-3 text-center backdrop-blur-sm">
          <span className="text-sm text-muted-foreground">
            Saved to vocabulary
          </span>
        </div>
      )}
    </div>
  );
}
