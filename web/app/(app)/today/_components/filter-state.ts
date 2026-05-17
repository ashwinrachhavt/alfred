/**
 * URL-backed filter state for the Today views.
 *
 * The URL is the single source of truth so back-button navigation works and
 * filter state survives refresh/deep-linking. Every component that needs
 * the current filter reads from ``useSearchParams`` and calls
 * ``parseFiltersFromSearchParams``.
 *
 * Query params recognized:
 *   - ``kind``       (repeatable) — kind chip selection
 *   - ``status``     (repeatable) — status chip selection
 *   - ``tag``        (repeatable) — tag filter
 *   - ``q``          — search text
 *   - ``todos_only`` — ``1``/``0`` (excludes artifact_ref rows when ``1``)
 *   - ``task_priority`` / ``task_project_id`` / ``task_source_kind`` — task-backed todo filters
 *   - ``view``       — passthrough (table/kanban/calendar) — not owned here
 */

export const KIND_VALUES = ["todo", "note", "learning", "artifact_ref"] as const;
export type FilterKind = (typeof KIND_VALUES)[number];

export const STATUS_VALUES = ["open", "doing", "done", "skipped"] as const;
export type FilterStatus = (typeof STATUS_VALUES)[number];

export interface TodayFilterState {
  kind: FilterKind[];
  status: FilterStatus[];
  tag: string[];
  q: string | null;
  todosOnly: boolean;
  taskPriority: string[];
  taskProjectId: number | null;
  taskSourceKind: string | null;
}

export const ENTRY_KIND_OPTIONS: { value: FilterKind; label: string }[] = [
  { value: "todo", label: "Todo" },
  { value: "note", label: "Note" },
  { value: "learning", label: "Learning" },
  // Note: label is plural "Artifacts" to read as a category, not a kind name.
  { value: "artifact_ref", label: "Artifacts" },
];

export const ENTRY_STATUS_OPTIONS: { value: FilterStatus; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "doing", label: "Doing" },
  { value: "done", label: "Done" },
  { value: "skipped", label: "Skipped" },
];

type ParamsLike = URLSearchParams | { getAll: (key: string) => string[]; get: (key: string) => string | null };

function getAll(params: ParamsLike, key: string): string[] {
  const raw = params.getAll(key);
  return raw.filter((v) => v.length > 0);
}

function keepKnown<T extends string>(values: string[], allowed: readonly T[]): T[] {
  const set = new Set<string>(allowed);
  const out: T[] = [];
  const seen = new Set<string>();
  for (const v of values) {
    if (set.has(v) && !seen.has(v)) {
      seen.add(v);
      out.push(v as T);
    }
  }
  return out;
}

export function parseFiltersFromSearchParams(params: ParamsLike): TodayFilterState {
  const kind = keepKnown(getAll(params, "kind"), KIND_VALUES);
  const status = keepKnown(getAll(params, "status"), STATUS_VALUES);

  const tagSeen = new Set<string>();
  const tag: string[] = [];
  for (const raw of getAll(params, "tag")) {
    const cleaned = raw.trim().toLowerCase();
    if (cleaned && !tagSeen.has(cleaned)) {
      tagSeen.add(cleaned);
      tag.push(cleaned);
    }
  }

  const q = params.get("q");
  const todosOnly = params.get("todos_only") === "1";
  const taskProjectIdRaw = params.get("task_project_id");
  const taskProjectId = taskProjectIdRaw ? Number(taskProjectIdRaw) : null;
  const taskSourceKind = params.get("task_source_kind");

  return {
    kind,
    status,
    tag,
    q: q && q.length > 0 ? q : null,
    todosOnly,
    taskPriority: getAll(params, "task_priority").map((value) => value.toUpperCase()),
    taskProjectId: Number.isFinite(taskProjectId) ? taskProjectId : null,
    taskSourceKind: taskSourceKind && taskSourceKind.length > 0 ? taskSourceKind : null,
  };
}

export function serializeFiltersToQueryString(filters: TodayFilterState, extra?: Record<string, string>): string {
  const params = new URLSearchParams();
  if (extra) {
    for (const [k, v] of Object.entries(extra)) {
      if (v) params.set(k, v);
    }
  }
  for (const v of filters.kind) params.append("kind", v);
  for (const v of filters.status) params.append("status", v);
  for (const v of filters.tag) params.append("tag", v);
  if (filters.q) params.set("q", filters.q);
  if (filters.todosOnly) params.set("todos_only", "1");
  for (const v of filters.taskPriority) params.append("task_priority", v);
  if (typeof filters.taskProjectId === "number") params.set("task_project_id", String(filters.taskProjectId));
  if (filters.taskSourceKind) params.set("task_source_kind", filters.taskSourceKind);
  return params.toString();
}

export function toggleMultiValue<T extends string>(current: T[], value: T): T[] {
  if (current.includes(value)) {
    return current.filter((v) => v !== value);
  }
  return [...current, value];
}

/**
 * Project the filter state into the backend-visible list params.
 *
 * ``todos_only`` translates to ``include_artifacts: false``. Otherwise
 * artifacts are included by default (the backend also allows narrowing via
 * the ``kind`` filter).
 */
export function filterStateToListParams(filters: TodayFilterState): {
  kind?: string[];
  status?: string[];
  tag?: string[];
  q?: string;
  include_artifacts?: boolean;
  task_priority?: string[];
  task_project_id?: number;
  task_source_kind?: string;
} {
  const out: {
    kind?: string[];
    status?: string[];
    tag?: string[];
    q?: string;
    include_artifacts?: boolean;
    task_priority?: string[];
    task_project_id?: number;
    task_source_kind?: string;
  } = {};
  if (filters.kind.length > 0) out.kind = [...filters.kind];
  if (filters.status.length > 0) out.status = [...filters.status];
  if (filters.tag.length > 0) out.tag = [...filters.tag];
  if (filters.q) out.q = filters.q;
  if (filters.todosOnly) out.include_artifacts = false;
  if (filters.taskPriority.length > 0) out.task_priority = [...filters.taskPriority];
  if (typeof filters.taskProjectId === "number") out.task_project_id = filters.taskProjectId;
  if (filters.taskSourceKind) out.task_source_kind = filters.taskSourceKind;
  return out;
}
