"use client";

import Link from "next/link";

import { useQueries } from "@tanstack/react-query";
import { format, formatDistanceToNow } from "date-fns";
import {
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  ExternalLink,
  Link2,
  Tags,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { useZettelCard } from "@/features/zettels/queries";
import { type ApiZettelCard, getZettelCard } from "@/lib/api/zettels";
import { useShellStore } from "@/lib/stores/shell-store";
import { cn } from "@/lib/utils";
import type { Zettel } from "./mock-data";
import { BloomProgressBar } from "./bloom-badge";
import { ZettelLinkSuggestions } from "./zettel-link-suggestions";
import { ZettelReadContent } from "./zettel-read-content";

type Props = {
  zettelId: number;
  variant?: "page" | "dialog";
};

type ZettelMetadataProps = {
  zettel: Zettel;
  connectedCards: ApiZettelCard[];
  isConnectionsLoading: boolean;
  onOpenConnection: (cardId: number) => void;
  className?: string;
  sectionClassName?: string;
};

const sectionLabelClassName =
  "font-data text-[10px] font-medium tracking-[0.14em] text-[var(--alfred-text-tertiary)] uppercase";

function ZettelMetadata({
  zettel,
  connectedCards,
  isConnectionsLoading,
  onOpenConnection,
  className,
  sectionClassName,
}: ZettelMetadataProps) {
  const panelClassName = cn("rounded-lg border bg-card/90 p-4 shadow-sm", sectionClassName);

  return (
    <div className={cn("space-y-4", className)}>
      <section className={panelClassName}>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-primary flex size-7 items-center justify-center rounded-md bg-[var(--alfred-accent-subtle)]">
              <Tags className="size-3.5" />
            </span>
            <div className={sectionLabelClassName}>Tags</div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {zettel.tags.length > 0 ? (
              zettel.tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex max-w-full items-center gap-1.5 rounded-sm bg-[var(--alfred-accent-muted)] px-2 py-1 text-[10px] font-medium tracking-[0.05em] uppercase"
                >
                  <span className="bg-primary size-1 shrink-0 rounded-full" />
                  <span className="truncate">{tag}</span>
                </span>
              ))
            ) : (
              <span className="text-sm text-[var(--alfred-text-tertiary)]">No tags yet.</span>
            )}
          </div>
        </div>
      </section>

      <section className={panelClassName}>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="bg-secondary text-muted-foreground flex size-7 items-center justify-center rounded-md">
              <BookOpen className="size-3.5" />
            </span>
            <div className={sectionLabelClassName}>Source</div>
          </div>
          {zettel.source.url ? (
            <a
              href={zettel.source.url}
              target="_blank"
              rel="noreferrer"
              className="group bg-background/70 hover:border-primary/40 flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm transition-colors hover:bg-[var(--alfred-accent-subtle)]"
            >
              <span className="min-w-0 truncate">{zettel.source.title || "Open source"}</span>
              <ExternalLink className="text-primary size-3.5 shrink-0 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </a>
          ) : (
            <p className="text-sm leading-relaxed text-[var(--alfred-text-tertiary)]">
              No source link attached.
            </p>
          )}
        </div>
      </section>

      <section className={panelClassName}>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="bg-secondary text-muted-foreground flex size-7 items-center justify-center rounded-md">
              <Link2 className="size-3.5" />
            </span>
            <div className={sectionLabelClassName}>Connections</div>
          </div>
          {connectedCards.length > 0 ? (
            <div className="space-y-1.5">
              {connectedCards.map((card) => (
                <button
                  key={card.id}
                  type="button"
                  onClick={() => onOpenConnection(card.id)}
                  className="group bg-background/70 hover:border-primary/40 flex w-full items-center justify-between gap-3 rounded-md border px-3 py-2 text-left text-[12px] transition-colors hover:bg-[var(--alfred-accent-subtle)]"
                >
                  <span className="min-w-0 truncate">{card.title}</span>
                  <ArrowUpRight className="text-muted-foreground group-hover:text-primary size-3 shrink-0 transition-colors" />
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
    </div>
  );
}

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
      <div className={cn("space-y-5", isDialog && "p-5 sm:p-8")}>
        <div className="space-y-3">
          <div className="bg-secondary h-3 w-36 animate-pulse rounded" />
          <div className="bg-secondary h-10 w-4/5 max-w-2xl animate-pulse rounded" />
        </div>
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
          <div className="bg-card h-80 animate-pulse rounded-lg border" />
          <div className="space-y-4">
            <div className="bg-card h-28 animate-pulse rounded-lg border" />
            <div className="bg-card h-40 animate-pulse rounded-lg border" />
          </div>
        </div>
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

  const articleContent = (
    <article className="bg-card rounded-lg border p-4 shadow-sm sm:p-6 lg:p-7">
      <ZettelReadContent
        title={zettel.title}
        summary={zettel.summary}
        content={zettel.content}
        labelClassName={cn(sectionLabelClassName, "mb-3")}
        summarySectionClassName="border-l-2 border-primary bg-[var(--alfred-accent-subtle)] px-4 py-3 sm:px-5 sm:py-4"
        contentSectionClassName={
          zettel.summary.trim() && zettel.summary.trim() !== zettel.content.trim()
            ? "mt-6 border-t border-[var(--alfred-ruled-line)] pt-6"
            : undefined
        }
        summaryProseClassName="prose-p:my-0 prose-p:text-[15px] sm:prose-p:text-[16px] prose-p:leading-8 prose-li:text-[15px] prose-li:leading-7 prose-strong:text-[16px]"
        contentProseClassName="prose-headings:my-4 prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg prose-p:my-3 prose-p:text-[15px] sm:prose-p:text-[16px] prose-p:leading-7 prose-ul:my-3 prose-ol:my-3 prose-pre:my-4 prose-blockquote:my-4 prose-code:text-[12px]"
        emptyStateClassName="text-sm text-[var(--alfred-text-tertiary)]"
      />
    </article>
  );

  const bloomPanel = (
    <section className="bg-card/90 rounded-lg border p-4 shadow-sm sm:p-5">
      <BloomProgressBar level={zettel.bloomLevel} />
    </section>
  );

  const suggestionsPanel = (
    <section className="bg-card/90 rounded-lg border p-4 shadow-sm sm:p-5">
      <ZettelLinkSuggestions
        cardId={Number(zettel.id)}
        autoLoad
        className="space-y-3"
        labelClassName={sectionLabelClassName}
        emptyStateClassName="text-sm text-[var(--alfred-text-tertiary)]"
      />
    </section>
  );

  const readingContent = (
    <>
      {articleContent}
      {bloomPanel}
      {suggestionsPanel}
    </>
  );

  return (
    <div className={cn("flex h-full min-h-0 flex-col", !isDialog && "space-y-8")}>
      <div
        className={cn(
          "relative space-y-4",
          isDialog ? "bg-card/80 border-b px-4 py-4 pr-14 sm:px-6 sm:py-5 lg:px-8" : "",
        )}
      >
        {isDialog ? <div className="bg-primary/20 absolute inset-x-0 bottom-0 h-px" /> : null}
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 space-y-3">
            {variant === "page" ? (
              <Button asChild variant="ghost" size="sm" className="w-fit px-0">
                <Link href="/knowledge">
                  <ArrowLeft className="mr-2 size-4" />
                  Back to Knowledge
                </Link>
              </Button>
            ) : null}

            <div className="space-y-2">
              <h1 className="max-w-4xl font-serif text-2xl leading-tight text-pretty sm:text-3xl lg:text-[2.625rem]">
                {zettel.title}
              </h1>
              <p className="font-data flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] font-medium tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
                <span className="inline-flex items-center gap-1.5">
                  <CalendarDays className="size-3" />
                  Created {createdLabel}
                </span>
                <span>Updated {updatedLabel}</span>
              </p>
            </div>
          </div>

          <div className="grid shrink-0 grid-cols-2 gap-2 sm:flex sm:items-center">
            <div className="bg-background/70 rounded-md border px-3 py-2">
              <div className="font-data text-[9px] tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
                Connections
              </div>
              <div className="font-data text-sm tabular-nums">{zettel.connections.length}</div>
            </div>
            <div className="bg-background/70 rounded-md border px-3 py-2">
              <div className="font-data text-[9px] tracking-[0.12em] text-[var(--alfred-text-tertiary)] uppercase">
                Bloom
              </div>
              <div className="font-data text-sm tabular-nums">Level {zettel.bloomLevel}/6</div>
            </div>
            {isDialog ? (
              <Button
                asChild
                variant="outline"
                size="sm"
                className="bg-card col-span-2 h-full min-h-10 justify-center rounded-md px-3 text-xs sm:col-span-1"
              >
                <Link href={`/knowledge/${zettel.id}`} onClick={() => closeZettelViewer()}>
                  Open Page
                  <ArrowUpRight className="size-3.5" />
                </Link>
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      {isDialog ? (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto grid w-full max-w-6xl gap-5 px-4 py-4 sm:px-6 sm:py-6 lg:px-8 xl:grid-cols-[minmax(0,1fr)_minmax(260px,320px)]">
            <div className="min-w-0">{articleContent}</div>
            <aside className="min-w-0 space-y-4 xl:sticky xl:top-6 xl:self-start">
              {bloomPanel}
              <ZettelMetadata
                zettel={zettel}
                connectedCards={connectedCards}
                isConnectionsLoading={isConnectionsLoading}
                onOpenConnection={openZettelViewer}
              />
              {suggestionsPanel}
            </aside>
          </div>
        </div>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
          <div className="min-h-0 space-y-6">{readingContent}</div>
          <aside className="space-y-4">
            <ZettelMetadata
              zettel={zettel}
              connectedCards={connectedCards}
              isConnectionsLoading={isConnectionsLoading}
              onOpenConnection={openZettelViewer}
            />
          </aside>
        </div>
      )}
    </div>
  );
}
