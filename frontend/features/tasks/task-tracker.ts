import type { TaskStatusResponse } from "@/lib/api/types/tasks";

export type TaskSource =
  | "company_research"
  | "company_insights"
  | "interview_prep"
  | "mind_palace"
  | "admin"
  | "generic";

export type TrackedTask = {
  id: string;
  label: string;
  source: TaskSource;
  createdAt: string;
  /**
   * Optional deep-link to open when the user clicks "View".
   * Defaults to the Tasks page for the task.
   */
  href?: string;
  /**
   * Last status we saw, persisted for offline display.
   */
  lastStatus?: TaskStatusResponse;
};

export const TASK_TRACKER_STORAGE_KEY = "alfred:tasks:tracked:v1";
export const TASK_TRACKER_NOTIFIED_KEY = "alfred:tasks:notified:v1";

type StoredPayload = {
  version: 1;
  tasks: TrackedTask[];
};

function isTaskStatusResponse(value: unknown): value is TaskStatusResponse {
  return (
    value !== null &&
    typeof value === "object" &&
    "task_id" in value &&
    "status" in value &&
    "ready" in value &&
    "successful" in value &&
    "failed" in value
  );
}

function normalizeTask(task: TrackedTask): TrackedTask {
  return {
    id: task.id,
    label: task.label,
    source: task.source,
    createdAt: task.createdAt,
    href: task.href,
    lastStatus: isTaskStatusResponse(task.lastStatus) ? task.lastStatus : undefined,
  };
}

export function loadTrackedTasks(): TrackedTask[] {
  if (typeof window === "undefined") return [];
  const raw = window.localStorage.getItem(TASK_TRACKER_STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as StoredPayload;
    if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.tasks)) return [];
    return parsed.tasks.map(normalizeTask).filter((task) => task.id.trim().length > 0);
  } catch {
    return [];
  }
}

export function saveTrackedTasks(tasks: TrackedTask[]): void {
  if (typeof window === "undefined") return;
  const payload: StoredPayload = {
    version: 1,
    tasks,
  };
  window.localStorage.setItem(TASK_TRACKER_STORAGE_KEY, JSON.stringify(payload));
}

export function loadNotifiedTaskIds(): Set<string> {
  if (typeof window === "undefined") return new Set();
  const raw = window.localStorage.getItem(TASK_TRACKER_NOTIFIED_KEY);
  if (!raw) return new Set();
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((id) => typeof id === "string" && id.trim().length > 0));
  } catch {
    return new Set();
  }
}

export function saveNotifiedTaskIds(ids: Set<string>): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TASK_TRACKER_NOTIFIED_KEY, JSON.stringify(Array.from(ids)));
}
