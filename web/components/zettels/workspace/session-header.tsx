"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { cn } from "@/lib/utils";
import { useEndSession } from "@/features/workspace/mutations";
import type { ZettelSessionOut } from "@/lib/api/workspace";
import { useZettelWorkspaceStore } from "@/lib/stores/zettel-workspace-store";

type Props = {
  session: ZettelSessionOut;
  className?: string;
};

function formatElapsed(ms: number): string {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

export function SessionHeader({ session, className }: Props) {
  const router = useRouter();
  const endMutation = useEndSession();
  const reset = useZettelWorkspaceStore((s) => s.reset);
  const savedCards = useZettelWorkspaceStore((s) => s.savedCards);

  const startedAtMs = useMemo(() => {
    if (!session.created_at) return Date.now();
    const t = Date.parse(session.created_at);
    return Number.isFinite(t) ? t : Date.now();
  }, [session.created_at]);

  const [nowMs, setNowMs] = useState<number>(() => Date.now());
  useEffect(() => {
    if (session.ended_at) return; // freeze the clock on ended sessions
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [session.ended_at]);

  const elapsed = session.ended_at
    ? Math.max(0, Date.parse(session.ended_at) - startedAtMs)
    : nowMs - startedAtMs;

  const cardCount = savedCards.size || session.card_count || 0;
  const [title, setTitle] = useState<string>(session.title ?? "");

  useEffect(() => {
    setTitle(session.title ?? "");
  }, [session.title]);

  const handleEnd = async () => {
    if (session.ended_at) {
      router.push("/knowledge");
      return;
    }
    try {
      const result = await endMutation.mutateAsync(session.id);
      if (result.summary_card_id) {
        toast.success("Sitting ended", {
          description: "Summary card created.",
        });
      } else {
        toast.success("Sitting closed");
      }
      reset();
      router.push("/knowledge");
    } catch (err) {
      toast.error("Could not end sitting", {
        description: err instanceof Error ? err.message : String(err),
      });
    }
  };

  return (
    <header
      className={cn(
        "flex items-center justify-between gap-6 border-b border-[var(--alfred-ruled-line)] px-6 py-3",
        className,
      )}
    >
      {/* Left: meta ticker */}
      <div className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
        <span>SITTING</span>
        <span className="text-muted-foreground">·</span>
        <span className="tabular-nums">
          {cardCount} {cardCount === 1 ? "CARD" : "CARDS"}
        </span>
        <span className="text-muted-foreground">·</span>
        <span className="tabular-nums">{formatElapsed(elapsed)}</span>
      </div>

      {/* Center: editable title */}
      <input
        value={title}
        placeholder="Untitled sitting"
        onChange={(e) => setTitle(e.target.value)}
        className="flex-1 max-w-md border-none bg-transparent text-center font-serif text-base text-foreground placeholder:text-muted-foreground focus:outline-none"
        aria-label="Session title"
      />

      {/* Right: end button */}
      <button
        type="button"
        onClick={handleEnd}
        disabled={endMutation.isPending}
        className={cn(
          "rounded border border-[var(--alfred-ruled-line)] px-3 py-1.5 text-[11px] font-medium uppercase tracking-wider text-foreground transition-colors hover:bg-accent",
          "disabled:cursor-not-allowed disabled:opacity-60",
        )}
      >
        {endMutation.isPending ? "Ending..." : "End sitting"}
      </button>
    </header>
  );
}
