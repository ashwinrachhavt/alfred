"use client";

import type { CSSProperties } from "react";

import type { ExplorerDocumentItem } from "@/lib/api/types/documents";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function hashToHue(seed: string): number {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash << 5) - hash + seed.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash) % 360;
}

function coverGradientStyle(seed: string): CSSProperties {
  const hue = hashToHue(seed);
  const hue2 = (hue + 42) % 360;
  const hue3 = (hue + 150) % 360;

  return {
    backgroundImage: `linear-gradient(135deg,
      hsl(${hue} 78% 60%),
      hsl(${hue2} 82% 52%),
      hsl(${hue3} 72% 46%)
    )`,
  };
}

export function ShelfCard({ item, onSelect }: { item: ExplorerDocumentItem; onSelect: (id: string) => void }) {
  const topic = item.primary_topic?.trim() || null;
  const coverSeed = topic || item.title || item.id;
  const coverUrl = item.cover_image_url?.trim() || null;

  return (
    <button
      type="button"
      onClick={() => onSelect(item.id)}
      className={cn(
        "group bg-card relative flex w-full flex-col overflow-hidden rounded-xl border text-left shadow-sm transition",
        "hover:-translate-y-1 hover:shadow-lg",
      )}
    >
      <div className="relative aspect-[3/4] w-full overflow-hidden">
        {coverUrl ? (
          // Use <img> to avoid Next.js remotePatterns config for arbitrary user images.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={coverUrl}
            alt={item.title}
            loading="lazy"
            referrerPolicy="no-referrer"
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="h-full w-full" style={coverGradientStyle(coverSeed)} />
        )}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/30 via-black/0 to-white/5 opacity-80" />
      </div>

      <div className="flex flex-1 flex-col gap-2 p-3">
        <div className="flex items-start justify-between gap-2">
          <p className="line-clamp-2 text-sm leading-snug font-medium">{item.title}</p>
          {topic ? (
            <Badge variant="secondary" className="shrink-0">
              {topic}
            </Badge>
          ) : null}
        </div>
        {item.summary ? (
          <p className="text-muted-foreground line-clamp-2 text-xs leading-relaxed">{item.summary}</p>
        ) : null}
      </div>
    </button>
  );
}

