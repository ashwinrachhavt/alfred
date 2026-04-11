"use client";

import Link from "next/link";

import { useQueries } from "@tanstack/react-query";
import { format, formatDistanceToNow } from "date-fns";
import { ArrowLeft, ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useZettelCard } from "@/features/zettels/queries";
import { getZettelCard } from "@/lib/api/zettels";
import { useShellStore } from "@/lib/stores/shell-store";
import { cn } from "@/lib/utils";
import { BloomProgressBar } from "./bloom-badge";
import { ZettelLinkSuggestions } from "./zettel-link-suggestions";
import { ZettelReadContent } from "./zettel-read-content";

type Props = {
  zettelId: number;
  variant?: "page" | "dialog";
};

export function ZettelFullView({ zettelId, variant = "page" }: Props) {
  const closeZettelViewer = useShellStore((state) => state.closeZettelViewer);
  const openZettelViewer = useShellStore((state) => state.openZettelViewer);
  const isDialog = variant === "dialog";

  const {
    data: zettel,
    isLoading,
    isError,
  } = useZettelCard(Number.isFinite(zettelId) ? zettelId : null);
  const connectionQueries = useQueries({
    queries: (zettel?.connections ?? []).map((connectionId) => ({
      queryKey: ["zettels", "connection-card", Number(connectionId)],
      queryFn: () => getZettelCard(Number(connectionId)),
      staleTime: 10_000,
    })),
  });

  if (!Number.isFinite(zettelId)) {
    return <p className="text-muted-foreground text-sm">Invalid zettel id.</p>;
  }

  if (isLoading) {
    return (
      <div className={cn("space-y-4", isDialog && "p-6")}>
        <div className="bg-secondary h-4 w-28 animate-pulse rounded" />
        <div className="bg-secondary h-9 w-2/3 animate-pulse rounded" />
        <div className="bg-secondary h-40 w-full animate-pulse rounded-xl" />
      </div>
    );
  }

  if (isError || !zettel) {
    return (
      <div className={cn("space-y-4", isDialog && "p-6")}>
        {variant === "page" ? (
          <Button asChild variant="outline" size="sm">
            <Link href="/knowledge">
              <ArrowLeft className="mr-2 size-4" />
              Back to Knowledge
            </Link>
          </Button>
        ) : null}
        <p className="text-muted-foreground text-sm">Could not load this zettel.</p>
      </div>
    );
  }

  const createdLabel = format(new Date(zettel.createdAt), "MMMM d, yyyy 'at' h:mm a");
  const updatedLabel = formatDistanceToNow(new Date(zettel.updatedAt), { addSuffix: true });
  const connectedCards = connectionQueries
    .map((query) => query.data)
    .filter((card): card is NonNullable<typeof card> => Boolean(card));
  const isConnectionsLoading =
    zettel.connections.length > 0 &&
    connectionQueries.some((query) => query.isLoading && !query.data);

  return (
    <div className={cn("flex h-full min-h-0 flex-col", !isDialog && "space-y-8")}>
      <div className={cn("space-y-4", isDialog ? "border-b px-6 py-5" : "")}>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-3">
            {variant === "page" ? (
              <Button asChild variant="ghost" size="sm" className="w-fit px-0">
                <Link href="/knowledge">
                  <ArrowLeft className="mr-2 size-4" />
                  Back to Knowledge
                </Link>
              </Button>
            ) : null}

            <div className="space-y-2">
              <h1 className="max-w-4xl text-3xl leading-tight tracking-tight">{zettel.title}</h1>
              <p className="text-[11px] tracking-wider text-[var(--alfred-text-tertiary)] uppercase">
                Created {createdLabel} - Updated {updatedLabel}
              </p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {isDialog ? (
              <Button asChild variant="ghost" size="sm" className="text-xs">
                <Link href={`/knowledge/${zettel.id}`} onClick={() => closeZettelViewer()}>
                  Open Page
                </Link>
              </Button>
            ) : null}

            <div className="text-[10px] tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
              {zettel.connections.length} connection{zettel.connections.length === 1 ? "" : "s"}
            </div>
          </div>
        </div>
      </div>

      <div
        className={cn(
          "grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]",
          isDialog && "min-h-0 flex-1 overflow-hidden px-6 py-6",
        )}
      >
        <div className={cn("min-h-0", isDialog && "overflow-y-auto pr-1")}>
          <article className="bg-card space-y-6 rounded-xl border p-6">
            <ZettelReadContent
              summary={zettel.summary}
              content={zettel.content}
              labelClassName="mb-3 text-[10px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase"
              proseClassName="prose-headings:my-3 prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg prose-p:my-3 prose-ul:my-3 prose-ol:my-3 prose-pre:my-4 prose-blockquote:my-4 prose-code:text-[12px]"
              emptyStateClassName="text-sm text-[var(--alfred-text-tertiary)]"
            />
          </article>
        </div>

        <aside className={cn("space-y-4", isDialog && "overflow-y-auto pr-1")}>
          <section className="bg-card space-y-4 rounded-xl border p-4">
            <div className="space-y-2">
              <div className="text-[10px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
                Bloom Level
              </div>
              <BloomProgressBar level={zettel.bloomLevel} />
            </div>

            <div className="space-y-2">
              <div className="text-[10px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
                Tags
              </div>
              <div className="flex flex-wrap gap-1.5">
                {zettel.tags.length > 0 ? (
                  zettel.tags.map((tag) => (
                    <span
                      key={tag}
                      className="text-primary rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-0.5 text-[10px] font-medium tracking-wider uppercase"
                    >
                      {tag}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-[var(--alfred-text-tertiary)]">No tags yet.</span>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <div className="text-[10px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
                Source
              </div>
              {zettel.source.url ? (
                <a
                  href={zettel.source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary inline-flex items-center gap-1 text-sm hover:underline"
                >
                  Open source
                  <ExternalLink className="size-3.5" />
                </a>
              ) : (
                <p className="text-sm text-[var(--alfred-text-tertiary)]">No source link attached.</p>
              )}
            </div>

            <div className="space-y-2">
              <div className="text-[10px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
                Connections
              </div>
              {connectedCards.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {connectedCards.map((card) => (
                    <button
                      key={card.id}
                      type="button"
                      onClick={() => openZettelViewer(card.id)}
                      className="text-muted-foreground hover:border-primary hover:text-foreground rounded-md border px-2.5 py-1 text-[12px] transition-colors"
                    >
                      {card.title}
                    </button>
                  ))}
                </div>
              ) : isConnectionsLoading ? (
                <p className="text-sm text-[var(--alfred-text-tertiary)]">Loading connections...</p>
              ) : (
                <p className="text-sm text-[var(--alfred-text-tertiary)]">No connections yet.</p>
              )}
            </div>
          </section>

          <section className="bg-card rounded-xl border p-4">
            <ZettelLinkSuggestions
              cardId={Number(zettel.id)}
              autoLoad
              labelClassName="text-[10px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase"
              emptyStateClassName="text-sm text-[var(--alfred-text-tertiary)]"
            />
          </section>
        </aside>
      </div>
    </div>
  );
}
