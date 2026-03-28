"use client";

import { cn } from "@/lib/utils";
import { BloomBadge } from "./bloom-badge";
import type { Zettel } from "./mock-data";

type Props = {
  zettel: Zettel;
  isSelected: boolean;
  onClick: () => void;
};

export function ZettelCard({ zettel, isSelected, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex flex-col rounded-lg border p-4 text-left transition-all duration-150",
        isSelected
          ? "border-primary bg-[var(--alfred-accent-subtle)] shadow-sm"
          : "border-[var(--border)] hover:border-[var(--border-strong)] hover:bg-[var(--alfred-accent-subtle)]",
      )}
    >
      <h3 className="font-serif text-[15px] leading-snug">{zettel.title}</h3>
      <p className="mt-1.5 line-clamp-2 text-[13px] leading-relaxed text-muted-foreground">
        {zettel.summary}
      </p>
      <div className="mt-3 flex items-center gap-2">
        {zettel.tags.slice(0, 2).map((tag) => (
          <span
            key={tag}
            className="rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-primary"
          >
            {tag}
          </span>
        ))}
        {zettel.tags.length > 2 && (
          <span className="font-mono text-[9px] text-[var(--alfred-text-tertiary)]">
            +{zettel.tags.length - 2}
          </span>
        )}
        <BloomBadge level={zettel.bloomLevel} className="ml-auto" />
      </div>
    </button>
  );
}
