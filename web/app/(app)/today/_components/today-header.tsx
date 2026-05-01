"use client";
import Link from "next/link";

export function TodayHeader({ view }: { view: "table" | "kanban" | "calendar" }) {
  return (
    <header className="space-y-4 border-b border-[var(--alfred-ruled-line)] pb-4">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-xs uppercase tracking-widest text-[var(--alfred-text-tertiary)] font-mono">
            DAILY LEDGER
          </p>
          <h1 className="font-serif text-5xl text-foreground">Today</h1>
        </div>
        <nav className="flex gap-1 text-xs uppercase tracking-wider font-mono">
          <ViewLink view="table" active={view === "table"}>
            Table
          </ViewLink>
          <ViewLink view="kanban" active={view === "kanban"}>
            Kanban
          </ViewLink>
          <ViewLink view="calendar" active={view === "calendar"}>
            Calendar
          </ViewLink>
          <Link
            href="/today"
            className="px-3 py-1.5 rounded-md hover:bg-[var(--alfred-accent-subtle)]"
          >
            Audit
          </Link>
        </nav>
      </div>
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
      className={`px-3 py-1.5 rounded-md transition-colors ${
        active
          ? "bg-[var(--alfred-accent-subtle)] text-primary border-l-2 border-primary"
          : "text-[var(--alfred-text-tertiary)] hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground"
      }`}
    >
      {children}
    </Link>
  );
}
