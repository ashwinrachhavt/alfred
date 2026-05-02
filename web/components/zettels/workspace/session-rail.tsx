"use client";

import { useMemo } from "react";
import { Plus } from "lucide-react";

import { cn } from "@/lib/utils";
import { useZettelWorkspaceStore } from "@/lib/stores/zettel-workspace-store";
import type { StackEntry } from "@/lib/stores/zettel-workspace-store";
import {
  BLOOM_BG_CLASSES,
  BLOOM_COLOR_CLASSES,
  type BloomLevel,
} from "@/lib/bloom";

type Props = {
  className?: string;
};

function formatShortTime(epochMs: number | null): string {
  if (epochMs === null) return "--:--";
  const d = new Date(epochMs);
  return d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function isSameEntry(a: StackEntry | null, b: StackEntry | null): boolean {
  if (!a || !b) return false;
  if (a.type !== b.type) return false;
  if (a.type === "saved" && b.type === "saved") return a.id === b.id;
  if (a.type === "draft" && b.type === "draft") return a.clientId === b.clientId;
  return false;
}

export function SessionRail({ className }: Props) {
  const stackOrder = useZettelWorkspaceStore((s) => s.stackOrder);
  const activeDraft = useZettelWorkspaceStore((s) => s.activeDraft);
  const savedCards = useZettelWorkspaceStore((s) => s.savedCards);
  const focusedEntry = useZettelWorkspaceStore((s) => s.focusedEntry);
  const focusEntry = useZettelWorkspaceStore((s) => s.focusEntry);
  const startDraft = useZettelWorkspaceStore((s) => s.startDraft);
  const sharedContext = useZettelWorkspaceStore((s) => s.sharedContext);

  const entries = useMemo(() => stackOrder, [stackOrder]);

  return (
    <aside
      className={cn(
        "flex flex-col bg-background/60",
        className,
      )}
      aria-label="Session timeline"
    >
      <div className="border-b border-[var(--alfred-ruled-line)] px-5 py-3 font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
        Timeline
      </div>

      <ul className="flex-1 overflow-y-auto">
        {entries.length === 0 && (
          <li className="px-5 py-8 text-xs text-muted-foreground">
            No cards yet. Start writing to populate this sitting.
          </li>
        )}
        {entries.map((entry) => {
          const focused = isSameEntry(focusedEntry, entry);
          if (entry.type === "draft") {
            const isActive = activeDraft?.clientId === entry.clientId;
            const title =
              (isActive && activeDraft?.title) ||
              (isActive && activeDraft?.content.split("\n")[0]?.slice(0, 40)) ||
              "Drafting...";
            const time = isActive ? activeDraft?.lastLocalSaveAt : null;
            return (
              <li key={`draft-${entry.clientId}`}>
                <button
                  type="button"
                  onClick={() => focusEntry(entry)}
                  className={cn(
                    "group flex w-full items-start gap-3 border-l-2 px-5 py-2.5 text-left transition-colors",
                    focused
                      ? "border-primary bg-[var(--alfred-accent-subtle)]"
                      : "border-transparent hover:bg-accent/40",
                  )}
                >
                  <span
                    className={cn(
                      "mt-1.5 size-2 shrink-0 rounded-full",
                      isActive
                        ? "bg-primary animate-pulse"
                        : "bg-muted-foreground/60",
                    )}
                    aria-hidden="true"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-serif text-[13px] text-foreground">
                      {title || "Drafting..."}
                    </div>
                    <div className="mt-0.5 font-mono text-[10px] text-[var(--alfred-text-tertiary)]">
                      {isActive ? "Draft" : "Abandoned"} · {formatShortTime(time ?? null)}
                    </div>
                  </div>
                </button>
              </li>
            );
          }

          // saved
          const saved = savedCards.get(entry.id);
          if (!saved) return null;
          const archived = Boolean(saved.archivedAt);
          const bloomLevel = saved.bloom.inferredLevel as BloomLevel;
          return (
            <li key={`saved-${entry.id}`}>
              <button
                type="button"
                onClick={() => focusEntry(entry)}
                className={cn(
                  "group flex w-full items-start gap-3 border-l-2 px-5 py-2.5 text-left transition-colors",
                  focused
                    ? "border-primary bg-[var(--alfred-accent-subtle)]"
                    : "border-transparent hover:bg-accent/40",
                  archived && "opacity-40",
                )}
              >
                <span
                  className={cn(
                    "mt-1.5 size-2 shrink-0 rounded-full",
                    BLOOM_BG_CLASSES[bloomLevel],
                  )}
                  aria-hidden="true"
                />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-serif text-[13px] text-foreground">
                    {saved.title || "Untitled"}
                  </div>
                  <div
                    className={cn(
                      "mt-0.5 flex items-center gap-2 font-mono text-[10px]",
                      BLOOM_COLOR_CLASSES[bloomLevel],
                    )}
                  >
                    <span>B{bloomLevel}</span>
                    <span className="text-[var(--alfred-text-tertiary)]">
                      · {formatShortTime(saved.lastSavedAt)}
                    </span>
                    {archived && (
                      <span className="text-[var(--alfred-text-tertiary)]">
                        · archived
                      </span>
                    )}
                  </div>
                </div>
              </button>
            </li>
          );
        })}
      </ul>

      {/* Footer: shared context + new card */}
      <div className="border-t border-[var(--alfred-ruled-line)] px-5 py-3 space-y-3">
        {(sharedContext.topic || sharedContext.tags.length > 0) && (
          <div className="space-y-1.5">
            <div className="font-mono text-[9px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
              Shared context
            </div>
            <div className="flex flex-wrap gap-1.5">
              {sharedContext.topic && (
                <span className="rounded bg-[var(--alfred-accent-muted)] px-2 py-0.5 font-sans text-[10px] uppercase tracking-wide text-primary">
                  {sharedContext.topic}
                </span>
              )}
              {sharedContext.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded border border-[var(--alfred-ruled-line)] px-2 py-0.5 font-sans text-[10px] uppercase tracking-wide text-muted-foreground"
                >
                  #{tag}
                </span>
              ))}
            </div>
          </div>
        )}
        <button
          type="button"
          onClick={() => {
            startDraft();
          }}
          className="flex w-full items-center justify-center gap-2 rounded border border-dashed border-[var(--alfred-ruled-line)] px-3 py-2 font-sans text-[11px] font-medium uppercase tracking-wider text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
        >
          <Plus className="size-3" />
          New card
        </button>
      </div>
    </aside>
  );
}
