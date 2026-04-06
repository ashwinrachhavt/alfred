"use client";

import { useState } from "react";
import { ChevronRight, ExternalLink } from "lucide-react";

export function EncyclopediaSection({
  summary,
  word,
}: {
  summary: string;
  word: string;
}) {
  const [open, setOpen] = useState(false);
  const wikiUrl = `https://en.wikipedia.org/wiki/${encodeURIComponent(word)}`;

  return (
    <div className="rounded-md border bg-card">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted-foreground">
          <ChevronRight
            className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-90" : ""}`}
          />
          Encyclopedia
        </span>
      </button>
      {open && (
        <div className="border-t px-4 py-3">
          <p className="text-sm leading-relaxed text-muted-foreground">
            {summary.length > 600 ? `${summary.slice(0, 600)}...` : summary}
          </p>
          <a
            href={wikiUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex items-center gap-1 text-xs text-[#E8590C] hover:underline"
          >
            Read more on Wikipedia
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      )}
    </div>
  );
}
