"use client";
import Link from "next/link";

interface TodayHeaderProps {
  view: "table" | "kanban" | "calendar";
  date?: Date;
}

export function TodayHeader({ view, date }: TodayHeaderProps) {
  const now = date ?? new Date();

  // "THURSDAY · APRIL 30, 2026"
  const eyebrow = formatEyebrow(now);
  // "April 30"
  const headline = formatHeadline(now);

  return (
    <header className="space-y-6 border-b border-[var(--alfred-ruled-line)] pb-6">
      {/* Eyebrow row: mono day-of-week · long-date */}
      <p className="text-xs uppercase tracking-[0.18em] font-mono text-[var(--alfred-text-tertiary)]">
        {eyebrow}
      </p>

      {/* Primary row: serif H1 date + mono secondary label */}
      <div className="flex items-baseline justify-between">
        <h1 className="font-serif text-[2.625rem] leading-none text-foreground">
          {headline}
        </h1>
        <span className="font-mono text-xs uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
          DAILY LEDGER
        </span>
      </div>

      {/* Secondary row: view toggle (Table / Kanban / Calendar) + Audit */}
      <nav className="flex items-center gap-1 font-mono text-xs uppercase tracking-widest">
        <ViewLink view="table" active={view === "table"}>
          Table
        </ViewLink>
        <ViewLink view="kanban" active={view === "kanban"}>
          Kanban
        </ViewLink>
        <ViewLink view="calendar" active={view === "calendar"}>
          Calendar
        </ViewLink>

        {/* Divider — visually demotes Audit from the 3 primary views */}
        <span
          className="mx-2 h-4 w-px bg-[var(--alfred-ruled-line)]"
          aria-hidden="true"
        />

        <Link
          href="/today"
          className="rounded-md px-3 py-1.5 text-[var(--alfred-text-tertiary)] transition-colors hover:bg-secondary hover:text-foreground"
        >
          Audit
        </Link>
      </nav>
    </header>
  );
}

function ViewLink({
  view,
  active,
  children,
}: {
  view: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={`/today?view=${view}`}
      className={
        // Underline-style active indicator for horizontal nav.
        active
          ? "rounded-md border-b-2 border-primary bg-[var(--alfred-accent-subtle)] px-3 py-1.5 text-primary"
          : "rounded-md border-b-2 border-transparent px-3 py-1.5 text-[var(--alfred-text-tertiary)] transition-colors hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground"
      }
    >
      {children}
    </Link>
  );
}

function formatEyebrow(date: Date): string {
  const weekday = date
    .toLocaleDateString("en-US", { weekday: "long" })
    .toUpperCase();
  const month = date
    .toLocaleDateString("en-US", { month: "long" })
    .toUpperCase();
  const day = date.getDate();
  const year = date.getFullYear();
  return `${weekday} · ${month} ${day}, ${year}`;
}

function formatHeadline(date: Date): string {
  return date.toLocaleDateString("en-US", { month: "long", day: "numeric" });
}
