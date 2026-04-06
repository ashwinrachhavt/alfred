"use client";

import { Badge } from "@/components/ui/badge";

type SynonymGroup = { sense: string; words: string[] };

export function SynonymsSection({
  synonyms,
  antonyms,
  onWordClick,
}: {
  synonyms: SynonymGroup[] | null;
  antonyms: SynonymGroup[] | null;
  onWordClick: (word: string) => void;
}) {
  const hasSynonyms = synonyms && synonyms.length > 0;
  const hasAntonyms = antonyms && antonyms.length > 0;
  if (!hasSynonyms && !hasAntonyms) return null;

  return (
    <div className="space-y-3">
      {hasSynonyms && (
        <div>
          <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            Synonyms
          </span>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {synonyms.flatMap((g) =>
              g.words.map((w) => (
                <Badge
                  key={w}
                  variant="secondary"
                  className="cursor-pointer hover:bg-accent transition-colors"
                  onClick={() => onWordClick(w)}
                >
                  {w}
                </Badge>
              )),
            )}
          </div>
        </div>
      )}
      {hasAntonyms && (
        <div>
          <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            Antonyms
          </span>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {antonyms.flatMap((g) =>
              g.words.map((w) => (
                <Badge
                  key={w}
                  variant="outline"
                  className="cursor-pointer hover:bg-accent transition-colors"
                  onClick={() => onWordClick(w)}
                >
                  {w}
                </Badge>
              )),
            )}
          </div>
        </div>
      )}
    </div>
  );
}
