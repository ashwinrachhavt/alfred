"use client";

import { forwardRef, memo } from "react";

import { cn } from "@/lib/utils";
import { BloomBadge } from "./bloom-badge";
import type { Zettel } from "./mock-data";

type Props = {
  zettel: Zettel;
  isSelected: boolean;
  isPulsing?: boolean;
  onClick: () => void;
};

export const ZettelCard = memo(
  forwardRef<HTMLButtonElement, Props>(function ZettelCard(
    { zettel, isSelected, isPulsing, onClick },
    ref,
  ) {
    const preview = zettel.preview ?? zettel.summary;

    return (
      <button
        ref={ref}
        data-zettel-id={zettel.id}
        onClick={onClick}
        className={cn(
          "flex flex-col rounded-lg border p-4 text-left transition-all duration-150",
          isSelected
            ? "border-primary bg-[var(--alfred-accent-subtle)] shadow-sm"
            : "border-[var(--border)] hover:-translate-y-px hover:border-[var(--border-strong)] hover:bg-[var(--alfred-accent-subtle)] hover:shadow-sm",
          isPulsing && "zettel-pulse",
        )}
      >
        <div className="flex items-start gap-2">
          <h3 className="flex-1 text-[15px] leading-snug">{zettel.title}</h3>
          {zettel.status === "draft" && (
            <span className="shrink-0 rounded border border-dashed border-[var(--alfred-text-tertiary)] px-1.5 py-0.5 text-[9px] tracking-wider text-[var(--alfred-text-tertiary)] uppercase">
              Draft
            </span>
          )}
        </div>
        {preview ? (
          <p className="text-muted-foreground mt-1.5 line-clamp-2 text-[13px] leading-relaxed">
            {preview}
          </p>
        ) : null}
        <div className="mt-3 flex items-center gap-2">
          {zettel.tags.slice(0, 2).map((tag) => (
            <span
              key={tag}
              className="text-primary rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-0.5 text-[9px] font-medium tracking-wider uppercase"
            >
              {tag}
            </span>
          ))}
          {zettel.tags.length > 2 && (
            <span className="text-[9px] text-[var(--alfred-text-tertiary)]">
              +{zettel.tags.length - 2}
            </span>
          )}
          <BloomBadge level={zettel.bloomLevel} className="ml-auto" />
        </div>
      </button>
    );
  }),
);
