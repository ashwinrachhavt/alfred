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

export const ZettelCard = memo(forwardRef<HTMLButtonElement, Props>(
 function ZettelCard({ zettel, isSelected, isPulsing, onClick }, ref) {
 return (
 <button
 ref={ref}
 data-zettel-id={zettel.id}
 onClick={onClick}
 className={cn(
 "flex flex-col rounded-lg border p-4 text-left transition-all duration-150",
 isSelected
 ? "border-primary bg-[var(--alfred-accent-subtle)] shadow-sm"
 : "border-[var(--border)] hover:border-[var(--border-strong)] hover:bg-[var(--alfred-accent-subtle)] hover:-translate-y-px hover:shadow-sm",
 isPulsing && "zettel-pulse",
 )}
 >
 <div className="flex items-start gap-2">
 <h3 className="flex-1 text-[15px] leading-snug">{zettel.title}</h3>
 {zettel.status === "draft" && (
 <span className="shrink-0 rounded border border-dashed border-[var(--alfred-text-tertiary)] px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
 Draft
 </span>
 )}
 </div>
 <p className="mt-1.5 line-clamp-2 text-[13px] leading-relaxed text-muted-foreground">
 {zettel.summary}
 </p>
 <div className="mt-3 flex items-center gap-2">
 {zettel.tags.slice(0, 2).map((tag) => (
 <span
 key={tag}
 className="rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-0.5 font-medium text-[9px] uppercase tracking-wider text-primary"
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
 },
));
