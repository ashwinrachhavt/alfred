"use client";

import { useEffect, useMemo } from "react";
import { parseISO, startOfDay } from "date-fns";

import { TableView } from "./views/table-view";
import { KanbanView } from "./views/kanban-view";
import { CalendarView } from "./views/calendar-view";
import { TodayHeader } from "./today-header";
import { EntryFilterBar } from "./entry-filter-bar";
import { TodayReflection } from "./today-reflection";
import { EntryDrawer } from "./entry-drawer";
import { CommandBar } from "./command-bar";
import {
  TodayInteractionProvider,
  useTodayInteraction,
} from "./today-interaction-context";

type ViewMode = "table" | "kanban" | "calendar";

export function TodayViewShell(props: {
  view: ViewMode;
  date?: string;
  week?: string;
  month?: string;
}) {
  return (
    <TodayInteractionProvider>
      <ShellContent {...props} />
    </TodayInteractionProvider>
  );
}

function ShellContent({
  view,
  date,
  week,
  month,
}: {
  view: ViewMode;
  date?: string;
  week?: string;
  month?: string;
}) {
  const interaction = useTodayInteraction();
  const headerDate = useMemo(() => {
    if (!date) return undefined;
    try {
      return startOfDay(parseISO(date));
    } catch {
      return undefined;
    }
  }, [date]);

  // Global ⌘K / Ctrl+K binding. Only active while this shell is mounted.
  useEffect(() => {
    function onKey(e: globalThis.KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        interaction.toggleCommandBar();
        return;
      }
      if (e.key === "Escape") {
        // Let inputs close themselves first; the drawer handles its own Esc
        // via Radix Sheet. Only fire global close if nothing is focused on a
        // form control.
        const target = e.target as HTMLElement | null;
        if (
          target &&
          (target.tagName === "INPUT" ||
            target.tagName === "TEXTAREA" ||
            target.isContentEditable)
        ) {
          return;
        }
        if (interaction.commandBarOpen) interaction.closeCommandBar();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [interaction]);

  const drawerOpen = interaction.drawerTarget !== null;

  return (
    <div className="mx-auto max-w-6xl px-8 py-8 space-y-6">
      <TodayHeader view={view} date={headerDate} />
      <TodayReflection />
      <EntryFilterBar />
      {view === "table" && <TableView date={date} />}
      {view === "kanban" && <KanbanView week={week} />}
      {view === "calendar" && <CalendarView month={month} />}

      <EntryDrawer
        open={drawerOpen}
        entryId={interaction.drawerTarget}
        onOpenChange={(open) => {
          if (!open) interaction.closeDrawer();
        }}
      />
      <CommandBar />
    </div>
  );
}
