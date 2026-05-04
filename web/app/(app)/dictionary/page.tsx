"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, BookOpen, Grid, Loader2, Sparkles } from "lucide-react";

import { DictionaryEntry } from "@/components/dictionary/dictionary-entry";
import { DictionaryEntrySkeleton } from "@/components/dictionary/dictionary-entry-skeleton";
import { DictionarySearchBar } from "@/components/dictionary/dictionary-search-bar";
import { SaveBar } from "@/components/dictionary/save-bar";
import { VocabularyCollection } from "@/components/dictionary/vocabulary-collection";
import { useSaveEntry } from "@/features/dictionary/mutations";
import { useDictionaryStore } from "@/lib/stores/dictionary-store";
import {
  streamDictionaryLookup,
  type DictionaryResult,
  type DictionaryStreamPayloads,
  type SaveIntent,
} from "@/lib/api/dictionary";

type LookupPhase = "idle" | "lexicon" | "ai" | "encyclopedia" | "done" | "error";

function coerceLookupPhase(phase: string): LookupPhase {
  if (phase === "ai" || phase === "encyclopedia" || phase === "done") {
    return phase;
  }
  return "lexicon";
}

function LookupProgress({ phase, message }: { phase: LookupPhase; message: string }) {
  if (phase === "idle" || phase === "done") return null;

  const isError = phase === "error";
  const Icon = isError ? AlertCircle : Loader2;

  return (
    <div className="bg-card/90 mx-auto mb-6 flex max-w-2xl items-center justify-between rounded-md border px-3 py-2 text-sm shadow-sm backdrop-blur">
      <div className="text-muted-foreground flex min-w-0 items-center gap-2">
        <Icon className={`h-4 w-4 shrink-0 ${isError ? "" : "animate-spin"}`} />
        <span className="truncate">{message}</span>
      </div>
      <span className="text-foreground ml-3 inline-flex shrink-0 items-center gap-1 rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-1 font-mono text-[10px] tracking-wider uppercase">
        <Sparkles className="h-3 w-3 text-[var(--alfred-accent)]" />
        {phase}
      </span>
    </div>
  );
}

export default function DictionaryPage() {
  const [lookupWord, setLookupWord] = useState<string | null>(null);
  const [result, setResult] = useState<DictionaryResult | null>(null);
  const [phase, setPhase] = useState<LookupPhase>("idle");
  const [statusMessage, setStatusMessage] = useState("Ready");
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lookupIdRef = useRef(0);
  const activeTab = useDictionaryStore((s) => s.activeTab);
  const setActiveTab = useDictionaryStore((s) => s.setActiveTab);

  const saveMutation = useSaveEntry();
  const isLoading = phase === "lexicon" && !result;
  const isAiStreaming = phase === "ai";

  const handleLookup = useCallback(
    (word: string) => {
      const normalized = word.trim().toLowerCase();
      if (!normalized) return;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const lookupId = lookupIdRef.current + 1;
      lookupIdRef.current = lookupId;

      setLookupWord(normalized);
      setActiveTab("search");
      setResult(null);
      setPhase("lexicon");
      setStatusMessage("Checking dictionary sources");
      setError(null);
      saveMutation.reset();

      void streamDictionaryLookup(
        normalized,
        (event, data) => {
          if (lookupId !== lookupIdRef.current) return;

          if (event === "status") {
            const payload = data as DictionaryStreamPayloads["status"];
            setPhase(coerceLookupPhase(payload.phase));
            setStatusMessage(payload.message ?? "Working");
            return;
          }

          if (event === "lookup") {
            setResult(data as DictionaryResult);
            return;
          }

          if (event === "ai_start") {
            setPhase("ai");
            setStatusMessage("Streaming contextual explanation");
            setResult((current) => (current ? { ...current, ai_explanation: "" } : current));
            return;
          }

          if (event === "ai_delta") {
            const payload = data as DictionaryStreamPayloads["ai_delta"];
            setResult((current) =>
              current
                ? {
                    ...current,
                    ai_explanation: `${current.ai_explanation ?? ""}${payload.content}`,
                  }
                : current,
            );
            return;
          }

          if (event === "ai_done") {
            const payload = data as DictionaryStreamPayloads["ai_done"];
            setResult((current) =>
              current ? { ...current, ai_explanation: payload.content } : current,
            );
            return;
          }

          if (event === "wikipedia") {
            const payload = data as DictionaryStreamPayloads["wikipedia"];
            setResult((current) => {
              if (!current) return current;
              return {
                ...current,
                wikipedia_summary: payload.summary,
                source_urls: Array.from(new Set([...current.source_urls, payload.source_url])),
              };
            });
            return;
          }

          if (event === "done") {
            setResult(data as DictionaryResult);
            setPhase("done");
            setStatusMessage("Ready");
            return;
          }

          if (event === "error") {
            const payload = data as DictionaryStreamPayloads["error"];
            setPhase("error");
            setError(payload.message);
            setStatusMessage(payload.message);
          }
        },
        controller.signal,
      ).catch((err: unknown) => {
        if (controller.signal.aborted || lookupId !== lookupIdRef.current) {
          return;
        }
        setPhase("error");
        setError(err instanceof Error ? err.message : "Dictionary lookup failed");
        setStatusMessage("Dictionary lookup failed");
      });
    },
    [saveMutation, setActiveTab],
  );

  useEffect(() => () => abortRef.current?.abort(), []);

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
    <div className="bg-background flex h-[calc(100dvh-3.5rem)] flex-col">
      <div className="bg-background/80 flex items-center justify-between border-b px-6 py-4 backdrop-blur">
        <h2 className="font-serif text-xl font-semibold">Dictionary</h2>
        <div className="flex gap-1">
          <button
            aria-label="Open dictionary lookup"
            onClick={() => setActiveTab("search")}
            className={`rounded-md p-2 transition-colors ${
              activeTab === "search"
                ? "text-foreground bg-[var(--alfred-accent-subtle)]"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <BookOpen className="h-4 w-4" />
          </button>
          <button
            aria-label="Open vocabulary collection"
            onClick={() => setActiveTab("collection")}
            className={`rounded-md p-2 transition-colors ${
              activeTab === "collection"
                ? "text-foreground bg-[var(--alfred-accent-subtle)]"
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
            <LookupProgress phase={phase} message={statusMessage} />
            {isLoading && <DictionaryEntrySkeleton />}
            {error && (
              <div className="border-destructive/30 bg-destructive/10 text-destructive mx-auto max-w-2xl rounded-md border px-4 py-3 text-sm">
                {error}
              </div>
            )}
            {result && !isLoading && (
              <DictionaryEntry
                result={result}
                onWordClick={handleLookup}
                isAiStreaming={isAiStreaming}
              />
            )}
            {!result && !isLoading && !lookupWord && (
              <div className="py-24 text-center">
                <p className="text-muted-foreground/50 font-serif text-2xl">Look up any word</p>
                <p className="text-muted-foreground mt-2 text-sm">
                  Search to see definitions, etymology, and AI-powered explanations
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
        <div className="bg-background/95 sticky bottom-0 z-10 border-t px-4 py-3 text-center backdrop-blur-sm">
          <span className="text-muted-foreground text-sm">Saved to vocabulary</span>
        </div>
      )}
    </div>
  );
}
