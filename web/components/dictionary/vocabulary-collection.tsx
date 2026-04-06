"use client";

import { Badge } from "@/components/ui/badge";
import { useVocabularyEntries } from "@/features/dictionary/queries";
import { useDictionaryStore } from "@/lib/stores/dictionary-store";
import type { SaveIntent } from "@/lib/api/dictionary";

const BLOOM_LABELS = [
  "",
  "Remember",
  "Understand",
  "Apply",
  "Analyze",
  "Evaluate",
  "Create",
];

const intentFilters: { value: SaveIntent | null; label: string }[] = [
  { value: null, label: "All" },
  { value: "learning", label: "Learning" },
  { value: "reference", label: "Reference" },
  { value: "encountered", label: "Encountered" },
];

export function VocabularyCollection({
  onSelect,
}: {
  onSelect: (word: string) => void;
}) {
  const filterIntent = useDictionaryStore((s) => s.filterIntent);
  const setFilterIntent = useDictionaryStore((s) => s.setFilterIntent);

  const { data: entries, isLoading } = useVocabularyEntries(
    filterIntent ? { save_intent: filterIntent } : undefined,
  );

  return (
    <div className="mx-auto max-w-2xl">
      <div className="flex gap-1.5 mb-6">
        {intentFilters.map(({ value, label }) => (
          <button
            key={label}
            onClick={() => setFilterIntent(value)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium uppercase tracking-wider transition-colors ${
              filterIntent === value
                ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-md border bg-muted"
            />
          ))}
        </div>
      ) : entries && entries.length > 0 ? (
        <div className="grid grid-cols-2 gap-3">
          {entries.map((entry) => (
            <button
              key={entry.id}
              onClick={() => onSelect(entry.word)}
              className="group rounded-md border bg-card p-3 text-left hover:border-foreground/20 transition-colors"
            >
              <p className="font-serif text-lg font-medium group-hover:text-[#E8590C] transition-colors">
                {entry.word}
              </p>
              {entry.definitions?.[0]?.senses[0] && (
                <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                  {entry.definitions[0].senses[0].definition}
                </p>
              )}
              <div className="mt-2 flex items-center gap-1.5">
                {entry.domain_tags?.slice(0, 2).map((tag) => (
                  <Badge key={tag} variant="secondary" className="text-[10px]">
                    {tag}
                  </Badge>
                ))}
                <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                  {BLOOM_LABELS[entry.bloom_level] ?? ""}
                </span>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="py-16 text-center text-sm text-muted-foreground">
          No saved words yet. Look up a word and save it to start your
          vocabulary journal.
        </div>
      )}
    </div>
  );
}
