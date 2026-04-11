"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Check, Link2, Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useCreateZettelLink } from "@/features/zettels/mutations";
import { suggestZettelLinks, type LinkSuggestion } from "@/lib/api/zettels";
import { cn } from "@/lib/utils";

type Props = {
  cardId: number;
  autoLoad?: boolean;
  className?: string;
  labelClassName?: string;
  emptyStateClassName?: string;
};

export function ZettelLinkSuggestions({
  cardId,
  autoLoad = false,
  className,
  labelClassName = "text-[9px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase",
  emptyStateClassName = "text-[11px] text-[var(--alfred-text-tertiary)]",
}: Props) {
  const [suggestions, setSuggestions] = useState<LinkSuggestion[]>([]);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const [acceptedLinks, setAcceptedLinks] = useState<Set<number>>(new Set());

  const activeCardIdRef = useRef(cardId);
  const linkMutation = useCreateZettelLink(cardId);

  const loadSuggestions = useCallback(async () => {
    activeCardIdRef.current = cardId;
    setSuggestLoading(true);
    setSuggestError(null);

    try {
      const results = await suggestZettelLinks(cardId, { min_confidence: 0.4, limit: 8 });
      if (activeCardIdRef.current !== cardId) return;
      setSuggestions(results);
      setAcceptedLinks(new Set());
    } catch (error) {
      if (activeCardIdRef.current !== cardId) return;
      setSuggestions([]);
      setSuggestError(
        error instanceof Error ? error.message : "Could not load AI link suggestions.",
      );
    } finally {
      if (activeCardIdRef.current === cardId) {
        setSuggestLoading(false);
      }
    }
  }, [cardId]);

  const handleAcceptLink = useCallback(
    (toCardId: number) => {
      linkMutation.mutate(
        { to_card_id: toCardId, type: "ai-suggested", bidirectional: true },
        {
          onSuccess: () => {
            setAcceptedLinks((prev) => new Set(prev).add(toCardId));
          },
        },
      );
    },
    [linkMutation],
  );

  useEffect(() => {
    activeCardIdRef.current = cardId;
    setSuggestions([]);
    setSuggestError(null);
    setAcceptedLinks(new Set());
    setSuggestLoading(false);

    if (autoLoad) {
      void loadSuggestions();
    }
  }, [autoLoad, cardId, loadSuggestions]);

  return (
    <section className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between gap-2">
        <div className={labelClassName}>AI Suggestions</div>
        <Button
          variant="ghost"
          size="sm"
          className="text-primary h-6 gap-1 px-2 text-[10px]"
          onClick={() => void loadSuggestions()}
          disabled={suggestLoading}
        >
          {suggestLoading ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />}
          {suggestions.length > 0 ? "Refresh" : suggestError ? "Retry" : "Find Links"}
        </Button>
      </div>

      {suggestions.length > 0 ? (
        <div className="space-y-1.5">
          {suggestions.map((suggestion) => (
            <div
              key={suggestion.to_card_id}
              className="flex items-center gap-2 rounded-md border px-2.5 py-2"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-[12px] font-medium">{suggestion.to_title}</p>
                <p className="text-[10px] leading-relaxed text-[var(--alfred-text-tertiary)]">
                  {suggestion.reason} -{" "}
                  {Math.round(suggestion.scores.composite_score * 100)}%
                </p>
              </div>
              {acceptedLinks.has(suggestion.to_card_id) ? (
                <span className="flex shrink-0 items-center gap-1 text-[10px] text-green-500">
                  <Check className="size-3" />
                  Linked
                </span>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-primary h-6 shrink-0 gap-1 px-2 text-[10px]"
                  onClick={() => handleAcceptLink(suggestion.to_card_id)}
                  disabled={linkMutation.isPending}
                >
                  <Link2 className="size-3" />
                  Link
                </Button>
              )}
            </div>
          ))}
        </div>
      ) : null}

      {suggestLoading && suggestions.length === 0 ? (
        <p className={emptyStateClassName}>Finding related cards...</p>
      ) : null}

      {!suggestLoading && suggestError ? (
        <p className="text-[11px] text-[var(--error)]">{suggestError}</p>
      ) : null}

      {!suggestLoading && !suggestError && suggestions.length === 0 ? (
        <p className={emptyStateClassName}>
          {autoLoad
            ? "No strong AI link suggestions yet."
            : 'Click "Find Links" to discover related cards.'}
        </p>
      ) : null}
    </section>
  );
}
