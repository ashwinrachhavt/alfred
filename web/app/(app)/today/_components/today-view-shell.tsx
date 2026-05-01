"use client";

import { TableView } from "./views/table-view";
import { KanbanView } from "./views/kanban-view";
import { CalendarView } from "./views/calendar-view";
import { TodayHeader } from "./today-header";
import { EntryFilterBar } from "./entry-filter-bar";
import { TodayReflection } from "./today-reflection";

type ViewMode = "table" | "kanban" | "calendar";

export function TodayViewShell({
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
  return (
    <div className="mx-auto max-w-6xl px-8 py-8 space-y-6">
      <TodayHeader view={view} />
      <TodayReflection />
      <EntryFilterBar />
      {view === "table" && <TableView date={date} />}
      {view === "kanban" && <KanbanView week={week} />}
      {view === "calendar" && <CalendarView month={month} />}
    </div>
  );
}
