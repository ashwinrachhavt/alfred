"use client";

import { ChevronDown, ChevronRight, Link2, Loader2, Sparkles } from "lucide-react";
import { useState } from "react";
import { useBacklinks } from "@/features/zettels/queries";

type Props = {
  cardId: number | null;
  onNavigate?: (sourceType: string, sourceId: string) => void;
};

export function BacklinksPanel({ cardId, onNavigate }: Props) {
  const { data, isLoading, isError } = useBacklinks(cardId);
  const [backlinksOpen, setBacklinksOpen] = useState(true);
  const [aiOpen, setAiOpen] = useState(true);

  if (!cardId) return null;

  const backlinks = data?.backlinks ?? [];
  const aiConnections = data?.ai_connections ?? [];

  return (
    <div className="flex flex-col gap-1 text-sm">
      {/* Backlinks section */}
      <button
        type="button"
        onClick={() => setBacklinksOpen(!backlinksOpen)}
        className="flex items-center gap-1.5 px-2 py-1 text-left"
      >
        {backlinksOpen ? (
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3 w-3 text-muted-foreground" />
        )}
        <Link2 className="h-3 w-3 text-muted-foreground" />
        <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Backlinks
        </span>
        {backlinks.length > 0 && (
          <span className="ml-auto text-[10px] text-[var(--alfred-text-tertiary)]">
            {backlinks.length}
          </span>
        )}
      </button>

      {backlinksOpen && (
        <div className="space-y-0.5 pl-2">
          {isLoading && (
            <div className="flex items-center gap-2 px-2 py-1.5">
              <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
              <span className="text-xs text-muted-foreground">Loading...</span>
            </div>
          )}

          {isError && (
            <div className="px-2 py-1.5 text-xs text-destructive">
              Failed to load backlinks
            </div>
          )}

          {!isLoading && backlinks.length === 0 && (
            <div className="px-2 py-1.5 text-[11px] text-[var(--alfred-text-tertiary)]">
              No backlinks yet. Link to this card from another note using [[title]].
            </div>
          )}

          {backlinks.map((bl, idx) => (
            <button
              key={`${bl.source_type}-${bl.source_id}-${idx}`}
              type="button"
              onClick={() => onNavigate?.(bl.source_type, bl.source_id)}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground"
            >
              <span className="truncate">{bl.source_title}</span>
              <span className="ml-auto shrink-0 text-[9px] uppercase text-[var(--alfred-text-tertiary)]">
                {bl.source_type}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* AI Connections section */}
      {aiConnections.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setAiOpen(!aiOpen)}
            className="flex items-center gap-1.5 px-2 py-1 text-left"
          >
            {aiOpen ? (
              <ChevronDown className="h-3 w-3 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-3 w-3 text-muted-foreground" />
            )}
            <Sparkles className="h-3 w-3 text-primary" />
            <span className="text-[10px] font-medium uppercase tracking-wider text-primary">
              AI Connections
            </span>
          </button>

          {aiOpen && (
            <div className="space-y-0.5 pl-2">
              {aiConnections.map((conn) => (
                <button
                  key={conn.id}
                  type="button"
                  onClick={() => onNavigate?.("zettel", String(conn.id))}
                  className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground"
                >
                  <div className="min-w-0">
                    <div className="truncate">{conn.title}</div>
                    {conn.topic && (
                      <div className="text-[9px] uppercase text-[var(--alfred-text-tertiary)]">
                        {conn.topic}
                      </div>
                    )}
                  </div>
                  <span className="ml-2 shrink-0 text-[9px] text-primary">
                    {Math.round(conn.score * 100)}%
                  </span>
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
