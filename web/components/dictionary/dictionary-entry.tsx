"use client";

import { Sparkles, Volume2 } from "lucide-react";
import type { DictionaryResult } from "@/lib/api/dictionary";
import { AiExplanationSection } from "./ai-explanation-section";
import { DefinitionSection } from "./definition-section";
import { EncyclopediaSection } from "./encyclopedia-section";
import { EtymologySection } from "./etymology-section";
import { SynonymsSection } from "./synonyms-section";
import { UsageNotesSection } from "./usage-notes-section";

export function DictionaryEntry({
  result,
  onWordClick,
  isAiStreaming,
}: {
  result: DictionaryResult;
  onWordClick: (word: string) => void;
  isAiStreaming?: boolean;
}) {
  const playAudio = () => {
    if (result.pronunciation_audio_url) {
      const audio = new Audio(result.pronunciation_audio_url);
      audio.play();
    }
  };

  return (
    <article className="mx-auto max-w-2xl space-y-8 pb-24">
      <header className="border-border/70 border-b pb-6">
        <h1 className="font-serif text-5xl font-semibold tracking-tight md:text-6xl">
          {result.word}
        </h1>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {result.pronunciation_ipa && (
            <span className="text-muted-foreground font-mono text-sm">
              {result.pronunciation_ipa}
            </span>
          )}
          {result.pronunciation_audio_url && (
            <button
              aria-label={`Play pronunciation for ${result.word}`}
              onClick={playAudio}
              className="text-muted-foreground hover:bg-accent hover:text-foreground rounded-md p-1 transition-colors"
            >
              <Volume2 className="h-4 w-4" />
            </button>
          )}
          {isAiStreaming && (
            <span className="text-foreground inline-flex items-center gap-1 rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-1 font-mono text-[10px] tracking-wider uppercase">
              <Sparkles className="h-3 w-3 text-[var(--alfred-accent)]" />
              AI streaming
            </span>
          )}
        </div>
      </header>
      <DefinitionSection groups={result.definitions} />
      {result.etymology && <EtymologySection etymology={result.etymology} />}
      <SynonymsSection
        synonyms={result.synonyms}
        antonyms={result.antonyms}
        onWordClick={onWordClick}
      />
      {(result.ai_explanation || isAiStreaming) && (
        <AiExplanationSection
          explanation={result.ai_explanation ?? ""}
          isStreaming={isAiStreaming}
        />
      )}
      {result.usage_notes && <UsageNotesSection notes={result.usage_notes} />}
      {result.wikipedia_summary && (
        <EncyclopediaSection summary={result.wikipedia_summary} word={result.word} />
      )}
    </article>
  );
}
