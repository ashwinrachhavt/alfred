"use client";

/**
 * COLOR BUDGET — TodayReflection (Midnight Editorial)
 *
 * No accent color. Reflection is a reference card, not an action.
 * All grays via --alfred-* vars + semantic Tailwind classes
 * (bg-card, text-foreground, text-muted-foreground).
 */

import { useMemo } from "react";
import { format, subDays } from "date-fns";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useTodayReflection } from "@/features/today/queries";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

function toIsoDay(value: Date): string {
  return format(value, "yyyy-MM-dd");
}

type EntryCounts = {
  todo?: number;
  note?: number;
  learning?: number;
  artifact_ref?: number;
};

function readEntryCounts(stats: Record<string, unknown>): EntryCounts {
  const raw = stats["entry_counts"];
  if (raw && typeof raw === "object") {
    return raw as EntryCounts;
  }
  return {};
}

function formatCountLabel(counts: EntryCounts): string | null {
  const parts: string[] = [];
  if (typeof counts.todo === "number") parts.push(`${counts.todo} todos`);
  if (typeof counts.note === "number") parts.push(`${counts.note} notes`);
  if (typeof counts.learning === "number") parts.push(`${counts.learning} learnings`);
  if (typeof counts.artifact_ref === "number") {
    parts.push(`${counts.artifact_ref} artifacts`);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

export function TodayReflection() {
  const yesterday = useMemo(() => subDays(new Date(), 1), []);
  const yesterdayIso = toIsoDay(yesterday);

  const { data: reflection, isLoading } = useTodayReflection(yesterdayIso);

  if (isLoading) {
    return (
      <section
        aria-label="Yesterday's reflection"
        className={cn(
          "rounded-md border p-5",
          "bg-card border-[var(--alfred-ruled-line)]",
        )}
      >
        <Skeleton className="mb-3 h-3 w-40" />
        <Skeleton className="h-4 w-3/4" />
      </section>
    );
  }

  if (!reflection || !reflection.digest_md) {
    // No digest yet — keep the shell clean.
    return null;
  }

  const eyebrow = `YESTERDAY · ${format(yesterday, "EEE MMM d").toUpperCase()}`;
  const entryCountsLabel = formatCountLabel(readEntryCounts(reflection.stats));

  return (
    <section
      aria-label="Yesterday's reflection"
      className={cn(
        "rounded-md border p-5",
        "bg-card border-[var(--alfred-ruled-line)]",
      )}
    >
      <p
        className={cn(
          "mb-1 text-[10px] font-medium uppercase tracking-widest",
          "text-[var(--alfred-text-tertiary)]",
        )}
        style={{ fontFamily: "var(--font-berkeley-mono, ui-monospace, monospace)" }}
      >
        {eyebrow}
      </p>
      <h2
        className="mb-3 text-xl text-foreground"
        style={{ fontFamily: "var(--font-source-serif, serif)" }}
      >
        Reflection
      </h2>

      <div
        className={cn(
          "prose prose-sm max-w-none dark:prose-invert",
          "prose-p:text-foreground prose-li:text-foreground",
          "prose-headings:font-sans prose-li:marker:text-muted-foreground",
          // No accent color — keep links muted since the reflection is
          // informational, not a CTA.
          "prose-a:text-foreground prose-a:underline hover:prose-a:no-underline",
        )}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{reflection.digest_md}</ReactMarkdown>
      </div>

      <footer
        className={cn(
          "mt-4 flex flex-wrap items-center justify-between gap-2 border-t pt-3",
          "border-[var(--alfred-ruled-line)]",
        )}
      >
        {entryCountsLabel ? (
          <span
            className="text-xs text-muted-foreground"
            style={{ fontFamily: "var(--font-berkeley-mono, ui-monospace, monospace)" }}
          >
            {entryCountsLabel}
          </span>
        ) : (
          <span />
        )}
        <span
          className="text-[10px] text-[var(--alfred-text-tertiary)]"
          style={{ fontFamily: "var(--font-berkeley-mono, ui-monospace, monospace)" }}
          title="pipeline run id"
        >
          run {reflection.pipeline_run_id}
        </span>
      </footer>
    </section>
  );
}
