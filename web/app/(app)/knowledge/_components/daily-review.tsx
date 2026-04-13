"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useDailyDeck } from "@/features/learning/queries";
import { useCompleteReview, useGenerateQuiz } from "@/features/learning/mutations";
import type { DeckItem } from "@/lib/api/learning";

type ReviewState =
  | "loading"
  | "generating"
  | "question"
  | "revealed"
  | "grading"
  | "complete"
  | "empty"
  | "error";

type SessionStats = {
  reviewed: number;
  forgot: number;
  partial: number;
  nailed: number;
  weakTopics: Map<string, { forgot: number; total: number }>;
};

export function DailyReview() {
  const { data: deck, isLoading, error: fetchError } = useDailyDeck();
  const completeReview = useCompleteReview();
  const generateQuiz = useGenerateQuiz();

  const [state, setState] = useState<ReviewState>("loading");
  const [cardIndex, setCardIndex] = useState(0);
  const [items, setItems] = useState<DeckItem[]>([]);
  const [stats, setStats] = useState<SessionStats>({
    reviewed: 0,
    forgot: 0,
    partial: 0,
    nailed: 0,
    weakTopics: new Map(),
  });

  // Sync deck data
  useEffect(() => {
    if (isLoading) {
      setState("loading");
      return;
    }
    if (fetchError) {
      setState("error");
      return;
    }
    if (deck && deck.items.length === 0) {
      setState("empty");
      return;
    }
    if (deck && deck.items.length > 0) {
      setItems(deck.items);
      // Pre-generate quizzes for items that need it
      const needsGen = deck.items.filter((i) => i.needs_quiz_generation);
      if (needsGen.length > 0) {
        setState("generating");
        Promise.allSettled(
          needsGen.map((item) =>
            generateQuiz.mutateAsync({ topicId: item.topic_id }),
          ),
        ).then(() => {
          setState("question");
        });
      } else {
        setState("question");
      }
    }
  }, [deck, isLoading, fetchError]); // eslint-disable-line react-hooks/exhaustive-deps

  const currentCard = items[cardIndex] ?? null;

  const handleGrade = useCallback(
    (score: number) => {
      if (!currentCard || state !== "revealed") return;
      setState("grading");

      const gradeLabel = score >= 0.8 ? "nailed" : score >= 0.4 ? "partial" : "forgot";

      setStats((prev) => {
        const next = { ...prev, reviewed: prev.reviewed + 1, [gradeLabel]: prev[gradeLabel] + 1 };
        const topicStats = new Map(prev.weakTopics);
        const existing = topicStats.get(currentCard.topic_name) ?? { forgot: 0, total: 0 };
        topicStats.set(currentCard.topic_name, {
          forgot: existing.forgot + (score < 0.4 ? 1 : 0),
          total: existing.total + 1,
        });
        next.weakTopics = topicStats;
        return next;
      });

      completeReview.mutate(
        { reviewId: currentCard.review_id, score },
        {
          onSuccess: () => {
            if (cardIndex + 1 >= items.length) {
              setState("complete");
            } else {
              setCardIndex((i) => i + 1);
              setState("question");
            }
          },
          onError: () => {
            // Skip on error, advance to next card
            if (cardIndex + 1 >= items.length) {
              setState("complete");
            } else {
              setCardIndex((i) => i + 1);
              setState("question");
            }
          },
        },
      );
    },
    [currentCard, state, cardIndex, items.length, completeReview],
  );

  // Keyboard shortcuts
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (state === "question" && e.code === "Space") {
        e.preventDefault();
        setState("revealed");
      }
      if (state === "revealed") {
        if (e.key === "1") handleGrade(0.0); // Forgot
        if (e.key === "2") handleGrade(0.5); // Partial
        if (e.key === "3") handleGrade(1.0); // Nailed it
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [state, handleGrade]);

  // --- Render states ---

  if (state === "loading") {
    return (
      <div className="py-16 text-center">
        <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <p className="mt-4 text-xs text-[var(--alfred-text-tertiary)]">Loading your daily deck...</p>
      </div>
    );
  }

  if (state === "generating") {
    return (
      <div className="py-16 text-center">
        <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <p className="mt-4 text-xs text-[var(--alfred-text-tertiary)]">Generating questions from your knowledge...</p>
      </div>
    );
  }

  if (state === "empty") {
    return (
      <div className="py-16 text-center">
        <p className="font-serif text-xl text-muted-foreground">All caught up</p>
        <p className="mt-2 text-xs text-[var(--alfred-text-tertiary)]">
          No reviews due today. Come back tomorrow.
        </p>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="py-16 text-center">
        <p className="text-xl text-destructive">Something went wrong</p>
        <p className="mt-2 text-xs text-[var(--alfred-text-tertiary)]">
          Could not load your review deck.
        </p>
        <Button
          variant="outline"
          className="mt-4 text-xs"
          onClick={() => window.location.reload()}
        >
          Try again
        </Button>
      </div>
    );
  }

  if (state === "complete") {
    const recalledPct =
      stats.reviewed > 0
        ? Math.round(((stats.nailed + stats.partial) / stats.reviewed) * 100)
        : 0;

    const weakTopics = Array.from(stats.weakTopics.entries())
      .filter(([, v]) => v.forgot > 0)
      .sort((a, b) => b[1].forgot - a[1].forgot)
      .slice(0, 3);

    return (
      <div className="mx-auto max-w-md py-12">
        <h3 className="text-center font-medium text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
          Session Complete
        </h3>

        <div className="mt-6 grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="font-mono text-2xl tabular-nums">{stats.reviewed}</p>
            <p className="mt-1 font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
              Reviewed
            </p>
          </div>
          <div>
            <p className="font-mono text-2xl tabular-nums text-primary">{recalledPct}%</p>
            <p className="mt-1 font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
              Recalled
            </p>
          </div>
          <div>
            <p className="font-mono text-2xl tabular-nums">{stats.nailed}</p>
            <p className="mt-1 font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
              Nailed
            </p>
          </div>
        </div>

        {weakTopics.length > 0 && (
          <div className="mt-6 border-t border-[var(--alfred-ruled-line)] pt-4">
            {weakTopics.map(([name, v]) => (
              <div key={name} className="flex items-center justify-between py-1.5">
                <span className="text-sm text-muted-foreground">{name}</span>
                <span className="font-mono text-xs text-warning">
                  {v.forgot}/{v.total} forgot
                </span>
              </div>
            ))}
          </div>
        )}

        {deck && deck.total_due > deck.showing && (
          <p className="mt-6 text-center font-mono text-[10px] text-[var(--alfred-text-tertiary)]">
            {deck.total_due - deck.showing} more items due
          </p>
        )}
      </div>
    );
  }

  // Active review: question or revealed state
  if (!currentCard) return null;

  return (
    <div className="mx-auto max-w-lg py-8">
      {/* Progress */}
      <div className="mb-2">
        <div className="h-0.5 w-full rounded-full bg-secondary">
          <div
            className="h-full rounded-full bg-primary transition-all duration-300"
            style={{ width: `${((cardIndex + 1) / items.length) * 100}%` }}
          />
        </div>
        <div className="mt-2 flex justify-between font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
          <span>
            {cardIndex + 1} of {items.length}
          </span>
          <span>~{Math.max(1, Math.round((items.length - cardIndex) * 0.67))} min left</span>
        </div>
      </div>

      {/* Card */}
      <div className="mt-6 rounded-lg border p-8">
        <p className="mb-4 text-xs font-medium uppercase tracking-widest text-primary">
          {currentCard.topic_name}
        </p>

        <p className="font-serif text-xl leading-relaxed">
          {currentCard.question || `Review: ${currentCard.topic_name}`}
        </p>

        {state === "question" && (
          <Button
            variant="outline"
            className="mt-8 w-full text-xs"
            onClick={() => setState("revealed")}
          >
            Show Answer
            <span className="ml-2 font-mono text-[9px] text-[var(--alfred-text-tertiary)]">
              Space
            </span>
          </Button>
        )}

        {state === "revealed" && (
          <div className="mt-6">
            {currentCard.answer ? (
              <div className="rounded-md border-l-3 border-primary bg-[var(--alfred-accent-subtle)] p-4">
                <p className="mb-2 font-medium text-[9px] uppercase tracking-widest text-primary">
                  Answer
                </p>
                <p className="text-sm leading-relaxed">{currentCard.answer}</p>
              </div>
            ) : (
              <div className="rounded-md border-l-3 border-muted-foreground bg-secondary p-4">
                <p className="text-sm leading-relaxed text-muted-foreground">
                  Self-assess: try to recall, then check the source.
                </p>
              </div>
            )}

            {currentCard.source && (
              <div className="mt-3 flex items-center gap-2 rounded-md bg-secondary/50 px-3 py-2">
                <div className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded bg-[var(--alfred-accent-muted)] font-mono text-[8px] text-primary">
                  D
                </div>
                <p className="font-mono text-[10px] text-[var(--alfred-text-tertiary)]">
                  {currentCard.source.title ?? "Source document"}
                  {currentCard.source.captured_at &&
                    ` \u00b7 captured ${new Date(currentCard.source.captured_at).toLocaleDateString()}`}
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Grade buttons */}
      {state === "revealed" && (
        <div className="mt-4 grid grid-cols-3 gap-3">
          <Button
            variant="outline"
            className="border-destructive/30 text-xs hover:bg-destructive/10 hover:text-destructive"
            onClick={() => handleGrade(0.0)}
          >
            Forgot
            <span className="ml-1 font-mono text-[9px] opacity-50">1</span>
          </Button>
          <Button
            variant="outline"
            className="border-warning/30 text-xs hover:bg-warning/10 hover:text-warning"
            onClick={() => handleGrade(0.5)}
          >
            Partial
            <span className="ml-1 font-mono text-[9px] opacity-50">2</span>
          </Button>
          <Button
            className="text-xs"
            onClick={() => handleGrade(1.0)}
          >
            Nailed it
            <span className="ml-1 font-mono text-[9px] opacity-50">3</span>
          </Button>
        </div>
      )}

      {state === "grading" && (
        <div className="mt-4 flex justify-center">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      )}
    </div>
  );
}
