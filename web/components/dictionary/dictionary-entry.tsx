"use client";

import { Volume2 } from "lucide-react";
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
}: {
  result: DictionaryResult;
  onWordClick: (word: string) => void;
}) {
  const playAudio = () => {
    if (result.pronunciation_audio_url) {
      const audio = new Audio(result.pronunciation_audio_url);
      audio.play();
    }
  };

  return (
    <article className="mx-auto max-w-2xl space-y-8 pb-24">
      <header>
        <h1 className="font-serif text-5xl font-semibold tracking-tight">
          {result.word}
        </h1>
        {result.pronunciation_ipa && (
          <div className="mt-2 flex items-center gap-2">
            <span className="font-mono text-sm text-muted-foreground">
              {result.pronunciation_ipa}
            </span>
            {result.pronunciation_audio_url && (
              <button
                onClick={playAudio}
                className="rounded-full p-1 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
              >
                <Volume2 className="h-4 w-4" />
              </button>
            )}
          </div>
        )}
      </header>
      <DefinitionSection groups={result.definitions} />
      {result.etymology && <EtymologySection etymology={result.etymology} />}
      <SynonymsSection
        synonyms={result.synonyms}
        antonyms={result.antonyms}
        onWordClick={onWordClick}
      />
      {result.ai_explanation && (
        <AiExplanationSection explanation={result.ai_explanation} />
      )}
      {result.usage_notes && <UsageNotesSection notes={result.usage_notes} />}
      {result.wikipedia_summary && (
        <EncyclopediaSection
          summary={result.wikipedia_summary}
          word={result.word}
        />
      )}
    </article>
  );
}
