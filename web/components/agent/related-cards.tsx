"use client";

import { Sparkles } from "lucide-react";

import type { ArtifactCard, RelatedCard } from "@/lib/stores/agent-store";

export function RelatedCards({
 cards,
 onCardClick,
}: {
 cards: RelatedCard[];
 onCardClick: (artifact: ArtifactCard) => void;
}) {
 if (cards.length === 0) return null;

 return (
 <div className="mt-3 pt-3 border-t">
 <div className="flex items-center gap-1.5 mb-2">
 <Sparkles className="h-3 w-3 text-muted-foreground" />
 <span className="font-medium text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
 Related knowledge
 </span>
 </div>
 <div className="space-y-1.5">
 {cards.map((card) => (
 <button
 key={card.zettelId}
 onClick={() =>
 onCardClick({
 type: "zettel",
 action: "found",
 id: card.zettelId,
 title: card.title,
 summary: card.reason,
 topic: card.domain,
 tags: [],
 })
 }
 className="w-full text-left px-3 py-2 rounded-md bg-secondary hover:bg-muted transition-colors"
 >
 <div className="flex min-w-0 items-center gap-2">
 <span className="shrink-0 font-medium text-[10px] uppercase tracking-wider text-primary">
 {card.domain}
 </span>
 <span className="min-w-0 truncate text-xs text-foreground">
 {card.title}
 </span>
 </div>
 <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">
 {card.reason}
 </p>
 </button>
 ))}
 </div>
 </div>
 );
}
