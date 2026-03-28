"use client";

import { useState, useMemo } from "react";
import { formatDistanceToNow } from "date-fns";

import { cn } from "@/lib/utils";
import { BloomBadge } from "./bloom-badge";
import { BLOOM_LABELS, type Zettel } from "./mock-data";

type SortKey = "title" | "bloom" | "connections" | "reviewed";
type SortDir = "asc" | "desc";

type Props = {
  zettels: Zettel[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

export function ZettelTable({ zettels, selectedId, onSelect }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("bloom");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const sorted = useMemo(() => {
    const arr = [...zettels];
    arr.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "title":
          cmp = a.title.localeCompare(b.title);
          break;
        case "bloom":
          cmp = a.bloomLevel - b.bloomLevel;
          break;
        case "connections":
          cmp = a.connections.length - b.connections.length;
          break;
        case "reviewed":
          cmp = (a.lastReviewedAt ?? "").localeCompare(b.lastReviewedAt ?? "");
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [zettels, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(key === "bloom" ? "asc" : "desc");
    }
  };

  const headerClass = "cursor-pointer select-none font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] hover:text-foreground transition-colors text-left px-4 py-3";
  const arrow = (key: SortKey) => (sortKey === key ? (sortDir === "asc" ? " ↑" : " ↓") : "");

  return (
    <table className="w-full border-collapse">
      <thead>
        <tr className="border-b border-[var(--border)]">
          <th className={headerClass} onClick={() => toggleSort("title")}>Concept{arrow("title")}</th>
          <th className={cn(headerClass, "w-28")}>Topic</th>
          <th className={cn(headerClass, "w-24")} onClick={() => toggleSort("bloom")}>Bloom{arrow("bloom")}</th>
          <th className={cn(headerClass, "w-20")} onClick={() => toggleSort("connections")}>Conns{arrow("connections")}</th>
          <th className={cn(headerClass, "w-28")} onClick={() => toggleSort("reviewed")}>Reviewed{arrow("reviewed")}</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((z) => (
          <tr
            key={z.id}
            onClick={() => onSelect(z.id)}
            className={cn(
              "cursor-pointer border-b border-[var(--alfred-ruled-line)] transition-colors",
              selectedId === z.id
                ? "bg-[var(--alfred-accent-subtle)]"
                : "hover:bg-[var(--alfred-accent-subtle)]",
            )}
          >
            <td className="px-4 py-3 font-serif text-[14px]">{z.title}</td>
            <td className="px-4 py-3">
              <span className="rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-primary">
                {z.tags[0]}
              </span>
            </td>
            <td className="px-4 py-3">
              <BloomBadge level={z.bloomLevel} />
              <span className="ml-1.5 font-mono text-[10px] text-[var(--alfred-text-tertiary)]">
                {BLOOM_LABELS[z.bloomLevel]}
              </span>
            </td>
            <td className="px-4 py-3 font-data text-sm tabular-nums">{z.connections.length}</td>
            <td className="px-4 py-3 font-mono text-[11px] text-[var(--alfred-text-tertiary)]">
              {z.lastReviewedAt
                ? formatDistanceToNow(new Date(z.lastReviewedAt), { addSuffix: false }) + " ago"
                : <span className="text-[var(--destructive)]">never</span>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
