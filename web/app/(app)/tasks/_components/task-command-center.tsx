"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  useCreateTaskSystemTask,
  useMarkTaskSystemTaskDone,
  usePlanTaskSystemTasks,
} from "@/features/task-system/mutations";
import { useTaskSystemDefaultBoard, useTaskSystemTasks } from "@/features/task-system/queries";
import type { TaskItem, TaskPriority, TaskStatus, TaskType } from "@/features/task-system/types";

const laneOrder: Array<{ status: TaskStatus; title: string; description: string }> = [
  { status: "BACKLOG", title: "Backlog", description: "Ideas waiting for commitment" },
  { status: "TODO", title: "Todo", description: "Committed next actions" },
  { status: "IN_PROGRESS", title: "In Progress", description: "Active work in motion" },
  { status: "DONE", title: "Done", description: "Completed work and learnings" },
];

const priorityRank: Record<TaskPriority, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 };
const priorityTone: Record<TaskPriority, string> = {
  HIGH: "border-[var(--error)]/40 bg-[var(--error)]/10 text-[var(--error)]",
  MEDIUM: "border-[var(--warning)]/40 bg-[var(--warning)]/10 text-[var(--warning)]",
  LOW: "border-[var(--success)]/40 bg-[var(--success)]/10 text-[var(--success)]",
};

function pluralize(value: number, noun: string): string {
  return `${value} ${noun}${value === 1 ? "" : "s"}`;
}

function sourceHref(task: TaskItem): string | null {
  if (task.source_url) return task.source_url;
  if (!task.source_kind || !task.source_id) return null;
  if (task.source_kind === "zettel") return `/knowledge?card=${task.source_id}`;
  if (task.source_kind === "note") return `/notes/${task.source_id}`;
  if (task.source_kind === "document") return `/documents/${task.source_id}`;
  if (task.source_kind === "capture") return `/inbox?capture=${task.source_id}`;
  return null;
}

function TaskCard({
  task,
  onDone,
  onOpen,
}: {
  task: TaskItem;
  onDone: (taskId: number) => void;
  onOpen: (task: TaskItem) => void;
}) {
  return (
    <article
      className="group rounded-md border border-border bg-card p-4 text-left transition-colors hover:border-border-strong"
      onClick={() => onOpen(task)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="line-clamp-2 text-sm font-medium leading-5 text-foreground">{task.title}</h3>
          {task.description_md ? (
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">{task.description_md}</p>
          ) : null}
        </div>
        <button
          type="button"
          disabled={task.status === "DONE"}
          onClick={(event) => {
            event.stopPropagation();
            onDone(task.id);
          }}
          className="rounded-full border border-border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)] transition-colors hover:bg-[var(--alfred-accent-subtle)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          Done
        </button>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] ${priorityTone[task.priority]}`}>
          {task.priority}
        </span>
        {task.type ? (
          <span className="rounded-full border border-border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
            {task.type.replaceAll("_", " ")}
          </span>
        ) : null}
        {task.estimated_pomodoros ? (
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
            {pluralize(task.estimated_pomodoros, "pomodoro")}
          </span>
        ) : null}
      </div>
    </article>
  );
}

export function TaskCommandCenter() {
  const [title, setTitle] = useState("");
  const [brainDump, setBrainDump] = useState("");
  const [priority, setPriority] = useState<TaskPriority | "ALL">("ALL");
  const [type, setType] = useState<TaskType | "">("");
  const [typeFilter, setTypeFilter] = useState<TaskType | "ALL">("ALL");
  const [view, setView] = useState<"board" | "list" | "table">("board");
  const [selectedTask, setSelectedTask] = useState<TaskItem | null>(null);
  const drawerCloseRef = useRef<HTMLButtonElement | null>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);

  const defaultBoard = useTaskSystemDefaultBoard();
  const tasksQuery = useTaskSystemTasks({ limit: 200 });
  const createTask = useCreateTaskSystemTask();
  const markDone = useMarkTaskSystemTaskDone();
  const planTasks = usePlanTaskSystemTasks();

  const tasks = tasksQuery.data?.tasks ?? [];
  const visibleTasks = useMemo(() => {
    const filtered = tasks.filter((task) => {
      const matchesPriority = priority === "ALL" || task.priority === priority;
      const matchesType = typeFilter === "ALL" || task.type === typeFilter;
      return matchesPriority && matchesType;
    });
    return [...filtered].sort((a, b) => priorityRank[b.priority] - priorityRank[a.priority]);
  }, [priority, tasks, typeFilter]);

  const laneCounts = useMemo(() => {
    return laneOrder.reduce<Record<TaskStatus, number>>(
      (acc, lane) => ({ ...acc, [lane.status]: tasks.filter((task) => task.status === lane.status).length }),
      { BACKLOG: 0, TODO: 0, IN_PROGRESS: 0, DONE: 0, ARCHIVED: 0 },
    );
  }, [tasks]);

  const activeCount = tasks.filter((task) => task.status !== "DONE" && task.status !== "ARCHIVED").length;
  const highPriorityCount = tasks.filter((task) => task.priority === "HIGH" && task.status !== "DONE").length;
  const estimatedPomodoros = tasks.reduce((sum, task) => sum + (task.estimated_pomodoros ?? 0), 0);
  const completedCount = tasks.filter((task) => task.status === "DONE").length;
  const approximateXp = completedCount * 25;

  useEffect(() => {
    if (!selectedTask) return;
    lastFocusedRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    drawerCloseRef.current?.focus();
    function handleDrawerKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setSelectedTask(null);
    }
    window.addEventListener("keydown", handleDrawerKeyDown);
    return () => {
      window.removeEventListener("keydown", handleDrawerKeyDown);
      lastFocusedRef.current?.focus();
    };
  }, [selectedTask]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isTyping = Boolean(target?.closest("input, textarea, select, [contenteditable='true']"));
      if (isTyping || event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key.toLowerCase() === "q") {
        event.preventDefault();
        document.getElementById("tasks-quick-add-input")?.focus();
      }
      if (event.key.toLowerCase() === "p") {
        event.preventDefault();
        document.getElementById("tasks-planner-input")?.focus();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  function handleQuickAdd() {
    const trimmed = title.trim();
    if (!trimmed) return;
    createTask.mutate({
      title: trimmed,
      priority: priority === "ALL" ? "MEDIUM" : priority,
      type: type || undefined,
      board_id: defaultBoard.data?.id,
    });
    setTitle("");
  }

  function handlePlan() {
    const input = brainDump.trim();
    if (!input) return;
    planTasks.mutate({ input, create_tasks: true, board_id: defaultBoard.data?.id });
    setBrainDump("");
  }

  return (
    <main className="mx-auto flex max-w-[96rem] flex-col gap-8 px-8 py-8">
      <section className="rounded-lg border border-border bg-card p-8 shadow-sm">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.15em] text-[var(--alfred-text-tertiary)]">
              Task operating system
            </p>
            <h1 className="mt-3 font-serif text-[42px] leading-[1.15] text-foreground">
              Convert knowledge into execution.
            </h1>
            <p className="mt-4 max-w-2xl text-[15px] leading-6 text-muted-foreground">
              A quieter Alfred-native port of Neuralflow’s task pane: quick capture, planning,
              priority triage, kanban lanes, and focus metadata without the arcade surface.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3 lg:min-w-[28rem]">
            <div className="rounded-md border border-border bg-background/40 p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">Active</p>
              <p className="mt-2 font-serif text-3xl text-foreground">{activeCount}</p>
            </div>
            <div className="rounded-md border border-border bg-background/40 p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">Urgent</p>
              <p className="mt-2 font-serif text-3xl text-foreground">{highPriorityCount}</p>
            </div>
            <div className="rounded-md border border-border bg-background/40 p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">Pomodoros</p>
              <p className="mt-2 font-serif text-3xl text-foreground">{estimatedPomodoros}</p>
            </div>
            <div className="rounded-md border border-[var(--accent)]/30 bg-[var(--alfred-accent-subtle)] p-4 sm:col-span-3">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">Momentum</p>
                  <p className="mt-1 text-sm text-muted-foreground">Reward progress updates when tasks, focus blocks, and pomodoros complete.</p>
                </div>
                <div className="text-right">
                  <p className="font-serif text-2xl text-foreground">{approximateXp}</p>
                  <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">XP shown</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_24rem]">
        <div className="rounded-lg border border-border bg-card p-5">
          <div className="flex flex-col gap-3 md:flex-row">
            <input
              id="tasks-quick-add-input"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") handleQuickAdd();
              }}
              placeholder="Write the next action… (Q)
              className="min-h-10 flex-1 rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-[var(--accent)]"
            />
            <select
              value={type}
              onChange={(event) => setType(event.target.value as TaskType | "")}
              className="min-h-10 rounded-md border border-border bg-background px-3 text-sm text-foreground"
            >
              <option value="">Type</option>
              <option value="DEEP_WORK">Deep work</option>
              <option value="SHALLOW_WORK">Shallow work</option>
              <option value="LEARNING">Learning</option>
              <option value="SHIP">Ship</option>
              <option value="MAINTENANCE">Maintenance</option>
            </select>
            <button
              type="button"
              onClick={handleQuickAdd}
              disabled={!title.trim() || createTask.isPending}
              className="min-h-10 rounded-md bg-[var(--accent)] px-4 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              Quick add
            </button>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {(["ALL", "HIGH", "MEDIUM", "LOW"] as const).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={priority === value}
                onClick={() => setPriority(value)}
                className={`rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.12em] transition-colors ${
                  priority === value
                    ? "border-[var(--accent)] bg-[var(--alfred-accent-subtle)] text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                {value}
              </button>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {(["ALL", "DEEP_WORK", "SHALLOW_WORK", "LEARNING", "SHIP", "MAINTENANCE"] as const).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={typeFilter === value}
                onClick={() => setTypeFilter(value)}
                className={`rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.12em] transition-colors ${
                  typeFilter === value
                    ? "border-[var(--accent)] bg-[var(--alfred-accent-subtle)] text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                {value.replaceAll("_", " ")}
              </button>
            ))}
          </div>
          <div className="mt-4 flex gap-2 border-t border-border pt-4">
            {(["board", "list", "table"] as const).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={view === value}
                onClick={() => setView(value)}
                className={`rounded-md px-3 py-1.5 text-sm capitalize transition-colors ${
                  view === value
                    ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {value}
              </button>
            ))}
          </div>
        </div>

        <aside className="rounded-lg border border-border bg-card p-5">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.15em] text-[var(--alfred-text-tertiary)]">
            Planner dock
          </p>
          <textarea
            id="tasks-planner-input"
            value={brainDump}
            onChange={(event) => setBrainDump(event.target.value)}
            placeholder="Paste a messy plan. Alfred will extract concrete tasks. (P)"
            className="mt-3 min-h-28 w-full resize-none rounded-md border border-border bg-background p-3 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground focus:border-[var(--accent)]"
          />
          <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
            Shortcuts: Q quick add · P planner
          </div>
          <button
            type="button"
            onClick={handlePlan}
            disabled={!brainDump.trim() || planTasks.isPending}
            className="mt-3 w-full rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-[var(--alfred-accent-subtle)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Generate tasks
          </button>
        </aside>
      </section>

      {tasksQuery.isLoading ? (
        <section className="grid gap-4 lg:grid-cols-4">
          {laneOrder.map((lane) => (
              <article key={lane.status} className="rounded-lg border border-border bg-card p-5">
              <div className="h-4 w-24 animate-pulse rounded bg-muted" />
              <div className="mt-5 space-y-3">
                {[0, 1, 2].map((item) => (
                  <div key={item} className="h-24 animate-pulse rounded-md border border-border bg-background/40" />
                ))}
              </div>
            </article>
          ))}
        </section>
      ) : view === "board" ? (
        <section className="grid gap-4 lg:grid-cols-4">
          {laneOrder.map((lane) => (
          <article key={lane.status} className="rounded-lg border border-border bg-card p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-medium text-foreground">{lane.title}</h2>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{lane.description}</p>
              </div>
              <span className="font-mono text-sm tabular-nums text-[var(--alfred-text-tertiary)]">
                {laneCounts[lane.status]}
              </span>
            </div>
            <div className="mt-5 space-y-3">
              {visibleTasks.filter((task) => task.status === lane.status).slice(0, 4).map((task) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    onDone={(taskId) => markDone.mutate({ taskId })}
                    onOpen={setSelectedTask}
                  />
              ))}
              {visibleTasks.filter((task) => task.status === lane.status).length === 0 ? (
                <div className="rounded-md border border-dashed border-border bg-background/40 p-4 text-sm text-muted-foreground">
                  No tasks in this lane.
                </div>
              ) : null}
            </div>
            </article>
          ))}
        </section>
      ) : view === "list" ? (
        <section className="rounded-lg border border-border bg-card p-5">
          <div className="flex items-center justify-between border-b border-border pb-4">
            <h2 className="text-sm font-medium text-foreground">Task list</h2>
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
              {pluralize(visibleTasks.length, "task")}
            </span>
          </div>
          <div className="mt-4 space-y-3">
            {visibleTasks.map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                onDone={(taskId) => markDone.mutate({ taskId })}
                onOpen={setSelectedTask}
              />
            ))}
            {visibleTasks.length === 0 ? (
              <div className="rounded-md border border-dashed border-border bg-background/40 p-8 text-center text-sm text-muted-foreground">
                No tasks match these filters.
              </div>
            ) : null}
          </div>
        </section>
      ) : (
        <section className="overflow-hidden rounded-lg border border-border bg-card">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-background/40 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">
              <tr>
                <th className="px-4 py-3 font-medium">Task</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Priority</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Pomodoros</th>
              </tr>
            </thead>
            <tbody>
              {visibleTasks.map((task) => (
                <tr
                  key={task.id}
                  onClick={() => setSelectedTask(task)}
                  className="cursor-pointer border-b border-border transition-colors last:border-0 hover:bg-[var(--alfred-accent-subtle)]"
                >
                  <td className="px-4 py-3 font-medium text-foreground">{task.title}</td>
                  <td className="px-4 py-3 text-muted-foreground">{task.status.replaceAll("_", " ")}</td>
                  <td className="px-4 py-3 text-muted-foreground">{task.priority}</td>
                  <td className="px-4 py-3 text-muted-foreground">{task.type?.replaceAll("_", " ") ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-[var(--alfred-text-tertiary)]">
                    {task.estimated_pomodoros ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {visibleTasks.length === 0 ? (
            <div className="border-t border-border p-8 text-center text-sm text-muted-foreground">
              No tasks match these filters.
            </div>
          ) : null}
        </section>
      )}

      {tasksQuery.isError ? (
        <div className="rounded-md border border-[var(--error)]/30 bg-[var(--error)]/10 p-4 text-sm text-[var(--error)]">
          Could not load tasks. The task-system API may still be migrating.
        </div>
      ) : null}

      {selectedTask ? (
        <div className="fixed inset-0 z-50 flex justify-end bg-background/60 backdrop-blur-sm" role="dialog" aria-modal="true">
          <button
            type="button"
            aria-label="Close task details"
            className="absolute inset-0 cursor-default"
            onClick={() => setSelectedTask(null)}
          />
          <aside className="relative h-full w-full max-w-md border-l border-border bg-card p-6 shadow-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-[var(--alfred-text-tertiary)]">
                  Task detail
                </p>
                <h2 className="mt-2 text-2xl font-medium text-foreground">{selectedTask.title}</h2>
              </div>
              <button
                ref={drawerCloseRef}
                type="button"
                onClick={() => setSelectedTask(null)}
                className="rounded-md border border-border px-3 py-1 text-sm text-muted-foreground hover:text-foreground"
              >
                Close
              </button>
            </div>
            <div className="mt-6 space-y-5 text-sm">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">Description</p>
                <p className="mt-2 leading-6 text-muted-foreground">{selectedTask.description_md || "No description yet."}</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-md border border-border p-3">
                  <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">Status</p>
                  <p className="mt-1 text-foreground">{selectedTask.status.replaceAll("_", " ")}</p>
                </div>
                <div className="rounded-md border border-border p-3">
                  <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">Priority</p>
                  <p className="mt-1 text-foreground">{selectedTask.priority}</p>
                </div>
              </div>
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--alfred-text-tertiary)]">Source links</p>
                <div className="mt-2 space-y-2 text-muted-foreground">
                  {sourceHref(selectedTask) ? (
                    <a
                      href={sourceHref(selectedTask) ?? undefined}
                      className="block rounded-md border border-border px-3 py-2 text-foreground transition-colors hover:bg-[var(--alfred-accent-subtle)]"
                    >
                      {selectedTask.source_kind ?? "source"}: {selectedTask.source ?? selectedTask.source_id ?? selectedTask.source_url}
                    </a>
                  ) : (
                    <p>No source link yet.</p>
                  )}
                  {selectedTask.project_id ? (
                    <p className="rounded-md border border-border px-3 py-2">Project #{selectedTask.project_id}</p>
                  ) : null}
                  {selectedTask.tags.length > 0 ? (
                    <div className="flex flex-wrap gap-2 pt-2">
                      {selectedTask.tags.map((tag) => (
                        <span key={tag} className="rounded-full border border-border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em]">
                          {tag}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          </aside>
        </div>
      ) : null}
    </main>
  );
}
