"use client";

import { AlertCircle, CheckCircle2, CircleDashed, Link2, Sparkles } from "lucide-react";
import { Markdown } from "@copilotkit/react-ui";

import { cn } from "@/lib/utils";

export type StreamLinkSuggestion = {
  card_id: number;
  title: string;
  score: number;
  reason: string;
};

export type StreamEnrichment = {
  suggested_title: string | null;
  summary: string | null;
  suggested_tags: string[];
  suggested_topic: string | null;
};

export type StreamBloom = {
  level: number;
  rationale: string;
};

export type ZettelCreationStreamPanelState = {
  phase: "idle" | "pending" | "streaming" | "complete" | "error";
  title: string | null;
  cardId: number | null;
  thinking: string;
  links: StreamLinkSuggestion[];
  enrichment: StreamEnrichment | null;
  bloom: StreamBloom | null;
  errors: Array<{ step: string; message: string }>;
  steps: {
    saved: boolean;
    embedded: boolean;
    searched: boolean;
    enriched: boolean;
    completed: boolean;
  };
};

type Props = {
  state: ZettelCreationStreamPanelState;
  className?: string;
};

const stepLabels: Array<{
  key: keyof ZettelCreationStreamPanelState["steps"];
  label: string;
}> = [
  { key: "saved", label: "Saved draft" },
  { key: "embedded", label: "Embedded" },
  { key: "searched", label: "Linked" },
  { key: "enriched", label: "Enriched" },
  { key: "completed", label: "Finalized" },
];

function phaseLabel(phase: ZettelCreationStreamPanelState["phase"]): string {
  if (phase === "pending") return "Queued";
  if (phase === "streaming") return "Streaming";
  if (phase === "complete") return "Complete";
  if (phase === "error") return "Needs attention";
  return "Idle";
}

export function ZettelCreationStreamPanel({ state, className }: Props) {
  if (state.phase === "idle") return null;

  const hasWarnings = state.errors.length > 0;
  const isActive = state.phase === "pending" || state.phase === "streaming";

  return (
    <section
      className={cn(
        "rounded-md border border-[var(--alfred-ruled-line)] bg-[var(--bg-secondary)]/45 p-4",
        "shadow-[0_12px_40px_rgba(0,0,0,0.12)]",
        className,
      )}
      aria-label="Streaming zettel creation"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-primary flex items-center gap-2 font-mono text-[10px] tracking-wider uppercase">
            <Sparkles className={cn("size-3", isActive && "animate-pulse")} />
            <span>CopilotKit stream</span>
          </div>
          <h3 className="text-foreground mt-1 truncate font-serif text-[20px] leading-tight">
            {state.title || "Forming zettel"}
          </h3>
        </div>
        <div
          className={cn(
            "shrink-0 rounded border px-2 py-1 font-mono text-[10px] tracking-wider uppercase",
            state.phase === "error"
              ? "border-red-500/30 bg-red-500/10 text-red-500"
              : "border-primary/30 bg-primary/10 text-primary",
          )}
        >
          {phaseLabel(state.phase)}
          {state.cardId ? ` #${state.cardId}` : ""}
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-5">
        {stepLabels.map((step) => {
          const done = state.steps[step.key];
          return (
            <div
              key={step.key}
              className={cn(
                "flex min-w-0 items-center gap-1.5 rounded border px-2 py-1.5",
                done
                  ? "border-primary/25 bg-primary/10 text-foreground"
                  : "border-[var(--alfred-ruled-line)] text-[var(--alfred-text-tertiary)]",
              )}
            >
              {done ? (
                <CheckCircle2 className="text-primary size-3 shrink-0" />
              ) : (
                <CircleDashed className={cn("size-3 shrink-0", isActive && "animate-spin")} />
              )}
              <span className="truncate font-mono text-[9px] tracking-wider uppercase">
                {step.label}
              </span>
            </div>
          );
        })}
      </div>

      {state.enrichment?.summary ? (
        <div className="bg-background/45 mt-4 rounded border border-[var(--alfred-ruled-line)] p-3">
          <div className="font-mono text-[9px] tracking-wider text-[var(--alfred-text-tertiary)] uppercase">
            Summary
          </div>
          <p className="text-foreground mt-1 font-serif text-[15px] leading-[1.45]">
            {state.enrichment.summary}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {state.enrichment.suggested_topic ? (
              <span className="text-primary rounded bg-[var(--alfred-accent-muted)] px-2 py-0.5 font-sans text-[10px] tracking-wide uppercase">
                {state.enrichment.suggested_topic}
              </span>
            ) : null}
            {state.enrichment.suggested_tags.map((tag) => (
              <span
                key={tag}
                className="text-muted-foreground rounded border border-[var(--alfred-ruled-line)] px-2 py-0.5 font-sans text-[10px] tracking-wide uppercase"
              >
                #{tag}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {state.links.length > 0 ? (
        <div className="mt-4">
          <div className="mb-2 flex items-center gap-1.5 font-mono text-[9px] tracking-wider text-[var(--alfred-text-tertiary)] uppercase">
            <Link2 className="size-3" />
            <span>Connection candidates</span>
          </div>
          <ul className="space-y-2">
            {state.links.slice(0, 4).map((link) => (
              <li
                key={`${link.card_id}-${link.title}`}
                className="bg-background/35 rounded border border-[var(--alfred-ruled-line)] px-3 py-2"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-foreground truncate font-serif text-[14px]">
                    {link.title || `Zettel #${link.card_id}`}
                  </span>
                  <span className="text-primary font-mono text-[9px] tracking-wider uppercase">
                    {Math.round(link.score * 100)}%
                  </span>
                </div>
                {link.reason ? (
                  <p className="text-muted-foreground mt-1 line-clamp-2 text-[12px] leading-snug">
                    {link.reason}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {state.bloom ? (
        <div className="mt-4 border-t border-[var(--alfred-ruled-line)] pt-3 font-mono text-[10px] tracking-wider text-[var(--alfred-text-tertiary)] uppercase">
          Bloom level {state.bloom.level}
          {state.bloom.rationale ? ` - ${state.bloom.rationale}` : ""}
        </div>
      ) : null}

      {state.thinking ? (
        <details className="bg-background/35 mt-4 rounded border border-[var(--alfred-ruled-line)] p-3">
          <summary className="cursor-pointer font-mono text-[9px] tracking-wider text-[var(--alfred-text-tertiary)] uppercase">
            Live reasoning
          </summary>
          <div className="text-muted-foreground mt-3 max-h-44 overflow-y-auto text-[13px] leading-relaxed [&_.copilotKitParagraph]:text-[13px] [&_.copilotKitParagraph]:leading-relaxed">
            <Markdown content={state.thinking} />
          </div>
        </details>
      ) : null}

      {hasWarnings ? (
        <div className="mt-4 space-y-2">
          {state.errors.map((error, index) => (
            <div
              key={`${error.step}-${index}`}
              className="flex gap-2 rounded border border-red-500/25 bg-red-500/10 px-3 py-2 text-red-500"
            >
              <AlertCircle className="mt-0.5 size-3 shrink-0" />
              <div className="min-w-0">
                <div className="font-mono text-[9px] tracking-wider uppercase">
                  {error.step || "stream"}
                </div>
                <p className="mt-0.5 text-[12px] leading-snug">{error.message}</p>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
