"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, Brain, FileText, GitBranch, Sparkles } from "lucide-react";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

type Briefing = {
  date: string;
  generated_at: string;
  captures: { id: string; title: string; source_url: string | null; pipeline_status: string; created_at: string | null }[];
  connections: { link_id: number; from_card_id: number; from_title: string; to_card_id: number; to_title: string; type: string }[];
  reviews: { review_id: number; card_id: number; card_title: string; stage: number; due_at: string | null }[];
  gaps: { card_id: number; title: string }[];
  stats: {
    total_captures_24h: number;
    total_connections_24h: number;
    total_due_reviews: number;
    total_gaps: number;
    total_cards: number;
    total_links: number;
  };
};

function useTodayBriefing() {
  return useQuery({
    queryKey: ["today", "briefing"],
    queryFn: () => apiFetch<Briefing>(apiRoutes.today.briefing),
    staleTime: 60_000,
  });
}

function SectionHeader({ icon: Icon, title, count }: { icon: typeof FileText; title: string; count?: number }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon className="size-4 text-primary" />
      <span className="text-[10px] font-medium uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
        {title}
      </span>
      {count !== undefined && count > 0 && (
        <span className="rounded-full bg-primary px-1.5 py-0.5 text-[9px] font-semibold leading-none text-primary-foreground">
          {count}
        </span>
      )}
    </div>
  );
}

export function TodayDashboard() {
  const { data: briefing, isLoading, isError } = useTodayBriefing();

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div>
          <Skeleton className="h-10 w-48" />
          <Skeleton className="mt-2 h-4 w-64" />
        </div>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-3">
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (isError || !briefing) {
    return (
      <div className="flex flex-col items-center py-20 text-center">
        <p className="text-lg text-muted-foreground">Could not load today&apos;s briefing</p>
        <p className="mt-1 text-xs text-[var(--alfred-text-tertiary)]">Check that the backend is running</p>
      </div>
    );
  }

  const { captures, connections, reviews, gaps, stats } = briefing;
  const hasActivity = captures.length > 0 || connections.length > 0 || reviews.length > 0 || gaps.length > 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-[28px] tracking-tight">Today</h1>
        <p className="mt-1 text-xs text-[var(--alfred-text-tertiary)]">
          {stats.total_cards} cards · {stats.total_links} connections · {stats.total_captures_24h} captured today
        </p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Captured", value: stats.total_captures_24h, icon: FileText },
          { label: "Connected", value: stats.total_connections_24h, icon: GitBranch },
          { label: "Due Review", value: stats.total_due_reviews, icon: Brain },
          { label: "Gaps", value: stats.total_gaps, icon: Sparkles },
        ].map((s) => (
          <div key={s.label} className="rounded-lg border p-4">
            <div className="flex items-center gap-2">
              <s.icon className="size-4 text-[var(--alfred-text-tertiary)]" />
              <span className="text-[10px] font-medium uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
                {s.label}
              </span>
            </div>
            <p className="mt-2 font-mono text-2xl tabular-nums">{s.value}</p>
          </div>
        ))}
      </div>

      {!hasActivity && (
        <div className="rounded-lg border border-dashed p-8 text-center">
          <Sparkles className="mx-auto size-6 text-[var(--alfred-text-tertiary)]" />
          <p className="mt-3 text-sm text-muted-foreground">
            Nothing new today. Capture some knowledge with the + button or Cmd+Shift+K.
          </p>
        </div>
      )}

      {/* What You Captured */}
      {captures.length > 0 && (
        <section>
          <SectionHeader icon={FileText} title="What You Captured" count={captures.length} />
          <div className="space-y-1">
            {captures.map((c) => (
              <a
                key={c.id}
                href="/inbox"
                className="flex items-center gap-3 rounded-md border px-4 py-3 transition-colors hover:bg-[var(--alfred-accent-subtle)]"
              >
                <span className={`size-2 rounded-full shrink-0 ${
                  c.pipeline_status === "complete" ? "bg-[var(--success)]" :
                  c.pipeline_status === "error" ? "bg-destructive" : "bg-primary"
                }`} />
                <span className="flex-1 truncate text-[13px]">{c.title}</span>
                <span className="text-[10px] text-[var(--alfred-text-tertiary)]">
                  {c.pipeline_status}
                </span>
              </a>
            ))}
          </div>
        </section>
      )}

      {/* Connections Discovered */}
      {connections.length > 0 && (
        <section>
          <SectionHeader icon={GitBranch} title="Connections Discovered" count={connections.length} />
          <div className="space-y-1">
            {connections.map((c) => (
              <div
                key={c.link_id}
                className="flex items-center gap-3 rounded-md border px-4 py-3"
              >
                <a href={`/knowledge?card=${c.from_card_id}`} className="flex-1 truncate text-[13px] text-primary hover:underline">
                  {c.from_title}
                </a>
                <span className="text-[10px] text-[var(--alfred-text-tertiary)]">→</span>
                <a href={`/knowledge?card=${c.to_card_id}`} className="flex-1 truncate text-[13px] text-primary hover:underline">
                  {c.to_title}
                </a>
                <span className="text-[9px] rounded bg-muted px-1.5 py-0.5 text-[var(--alfred-text-tertiary)]">
                  {c.type}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Due for Review */}
      {reviews.length > 0 && (
        <section>
          <SectionHeader icon={Brain} title="Due for Review" count={reviews.length} />
          <div className="space-y-1">
            {reviews.map((r) => (
              <a
                key={r.review_id}
                href={`/knowledge?card=${r.card_id}`}
                className="flex items-center gap-3 rounded-md border px-4 py-3 transition-colors hover:bg-[var(--alfred-accent-subtle)]"
              >
                <BookOpen className="size-4 text-[var(--alfred-text-tertiary)]" />
                <span className="flex-1 truncate text-[13px]">{r.card_title}</span>
                <span className="text-[10px] text-[var(--alfred-text-tertiary)]">
                  Stage {r.stage}
                </span>
              </a>
            ))}
          </div>
        </section>
      )}

      {/* Knowledge Gaps */}
      {gaps.length > 0 && (
        <section>
          <SectionHeader icon={Sparkles} title="Knowledge Gaps" count={gaps.length} />
          <p className="mb-2 text-[11px] text-[var(--alfred-text-tertiary)]">
            Cards you referenced but haven&apos;t fleshed out yet
          </p>
          <div className="space-y-1">
            {gaps.map((g) => (
              <a
                key={g.card_id}
                href={`/knowledge?card=${g.card_id}`}
                className="flex items-center gap-3 rounded-md border border-dashed px-4 py-3 transition-colors hover:bg-[var(--alfred-accent-subtle)]"
              >
                <span className="size-2 rounded-full border border-dashed border-[var(--alfred-text-tertiary)]" />
                <span className="flex-1 truncate text-[13px] text-muted-foreground">{g.title}</span>
                <Button variant="ghost" size="sm" className="h-6 text-[10px] text-primary">
                  Fill In
                </Button>
              </a>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
