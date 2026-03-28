"use client";

import { formatDistanceToNow } from "date-fns";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { BloomProgressBar } from "./bloom-badge";
import type { Zettel } from "./mock-data";
import { MOCK_ZETTELS } from "./mock-data";

type Props = {
  zettel: Zettel;
  onClose: () => void;
  onSelectZettel: (id: string) => void;
};

export function ZettelDetailPanel({ zettel, onClose, onSelectZettel }: Props) {
  const connectedZettels = MOCK_ZETTELS.filter((z) => zettel.connections.includes(z.id));
  const capturedAgo = formatDistanceToNow(new Date(zettel.source.capturedAt), { addSuffix: true });
  const reviewedAgo = zettel.lastReviewedAt
    ? formatDistanceToNow(new Date(zettel.lastReviewedAt), { addSuffix: true })
    : "never";

  return (
    <aside className="flex h-full w-[320px] shrink-0 flex-col border-l bg-card">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b p-4">
        <h2 className="font-serif text-lg leading-snug">{zettel.title}</h2>
        <Button variant="ghost" size="icon" className="size-7 shrink-0" onClick={onClose}>
          <X className="size-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Bloom score */}
        <BloomProgressBar level={zettel.bloomLevel} />

        {/* Summary */}
        <div>
          <div className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
            Summary
          </div>
          <p className="text-[13px] leading-relaxed text-muted-foreground">
            {zettel.summary}
          </p>
        </div>

        {/* Connections */}
        {connectedZettels.length > 0 && (
          <div>
            <div className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
              Connections ({connectedZettels.length})
            </div>
            <div className="flex flex-wrap gap-1.5">
              {connectedZettels.map((c) => (
                <button
                  key={c.id}
                  onClick={() => onSelectZettel(c.id)}
                  className="rounded-md border px-2.5 py-1 text-[12px] text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
                >
                  {c.title}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Tags */}
        <div>
          <div className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
            Tags
          </div>
          <div className="flex flex-wrap gap-1.5">
            {zettel.tags.map((tag) => (
              <span
                key={tag}
                className="rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-primary"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>

        {/* Source */}
        <div>
          <div className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
            Source
          </div>
          <p className="text-[12px] text-[var(--alfred-text-tertiary)]">
            {zettel.source.title}
          </p>
          <p className="mt-1 font-mono text-[10px] text-[var(--alfred-text-tertiary)]">
            Captured {capturedAgo} · Reviewed {reviewedAgo}
          </p>
        </div>

        {/* Quiz stats */}
        {zettel.quizHistory.attempts > 0 && (
          <div>
            <div className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
              Quiz Performance
            </div>
            <p className="font-data text-lg tabular-nums">
              {zettel.quizHistory.correct}/{zettel.quizHistory.attempts}
              <span className="ml-2 font-mono text-[10px] text-[var(--alfred-text-tertiary)]">
                ({Math.round((zettel.quizHistory.correct / zettel.quizHistory.attempts) * 100)}% accuracy)
              </span>
            </p>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="border-t p-4 flex gap-2">
        <Button size="sm" className="flex-1 font-mono text-xs">
          Feynman Test
        </Button>
        <Button size="sm" variant="outline" className="font-mono text-xs">
          Review
        </Button>
        <Button size="sm" variant="outline" className="font-mono text-xs">
          Edit
        </Button>
      </div>
    </aside>
  );
}
