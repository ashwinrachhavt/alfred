import { apiFetch, apiPatchJson, apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

export type TaskPriority = "LOW" | "MEDIUM" | "HIGH";
export type TaskStatus = "BACKLOG" | "TODO" | "IN_PROGRESS" | "DONE" | "ARCHIVED";
export type TaskType = "DEEP_WORK" | "SHALLOW_WORK" | "LEARNING" | "SHIP" | "MAINTENANCE";

export type TaskBoard = {
  id: number;
  user_id: string;
  title: string;
  description: string | null;
  theme: string | null;
  is_default: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type TaskColumn = {
  id: number;
  board_id: number;
  name: string;
  position: number;
  created_at: string | null;
  updated_at: string | null;
};

export type TaskItem = {
  id: number;
  user_id: string;
  board_id: number;
  column_id: number;
  project_id: number | null;
  title: string;
  description_md: string;
  priority: TaskPriority;
  status: TaskStatus;
  type: TaskType | null;
  estimate_minutes: number | null;
  estimated_pomodoros: number | null;
  completed_pomodoros: number;
  story_points: number | null;
  due_at: string | null;
  due_date: string | null;
  tags: string[];
  topics: string[];
  primary_topic: string | null;
  source: string | null;
  source_kind: string | null;
  source_id: string | null;
  source_url: string | null;
  auto_generated: boolean;
  ai_planned: boolean;
  from_brain_dump: boolean;
  ai_state: string;
  ai_confidence: number | null;
  ai_next_action: string | null;
  completed_at: string | null;
  meta: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
};

export type TaskListResponse = {
  tasks: TaskItem[];
  total: number;
  next_cursor: string | null;
};

export type TaskCreate = Partial<Omit<TaskItem, "id" | "user_id" | "created_at" | "updated_at">> & {
  title: string;
};

export type TaskUpdate = Partial<Omit<TaskCreate, "title">> & {
  title?: string;
};

export type TaskMoveRequest = {
  column_id: number;
  board_id?: number | null;
  position?: number | null;
};

export type UserTaskGamificationProfile = {
  id: number;
  user_id: string;
  xp: number;
  level: number;
  longest_daily_streak: number;
  current_daily_streak: number;
  last_activity_date: string | null;
  total_tasks_completed: number;
  total_deep_work_blocks: number;
  total_pomodoros: number;
};

export type UserTaskReward = {
  id: number;
  user_id: string;
  reward_id: number;
  task_id: number | null;
  earned_at: string;
  source: string | null;
  note: string | null;
  metadata: Record<string, unknown>;
};

export type TaskDoneResponse = {
  task: TaskItem;
  profile: UserTaskGamificationProfile | null;
  rewards: UserTaskReward[];
};

export type PlannedTask = {
  title: string;
  description_md: string;
  priority: TaskPriority;
  type: TaskType | null;
  estimate_minutes: number | null;
  tags: string[];
  rationale: string | null;
};

export type TaskPlanRequest = {
  input: string;
  create_tasks?: boolean;
  board_id?: number | null;
  project_id?: number | null;
};

export type TaskPlanResponse = {
  tasks: PlannedTask[];
  created_tasks: TaskItem[];
  rationale: string | null;
  raw_output: string | null;
};

export type TaskCalendarEventCreate = {
  title: string;
  start_at: string;
  end_at: string;
  task_id?: number | null;
  tz_name?: string;
  description_md?: string | null;
  location?: string | null;
  tags?: string[];
};

export type TaskCalendarEvent = TaskCalendarEventCreate & {
  id: number;
  user_id: string;
  type: string;
  created_at: string | null;
  updated_at: string | null;
};

export type TaskFocusSessionCreate = {
  task_id?: number | null;
  event_id?: number | null;
  started_at?: string | null;
};

export type TaskFocusSession = {
  id: number;
  user_id: string;
  task_id: number | null;
  event_id: number | null;
  started_at: string;
  ended_at: string | null;
  completed: boolean;
  interruptions: number;
  created_at: string | null;
  updated_at: string | null;
};

export type TaskPomodoroCreate = {
  task_id: number;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  reflection_md?: string | null;
  status?: string;
};

export type TaskPomodoro = TaskPomodoroCreate & {
  id: number;
  user_id: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
};

function buildTaskListQuery(params: {
  status?: TaskStatus[];
  priority?: TaskPriority[];
  board_id?: number;
  project_id?: number;
  source_kind?: string;
  limit?: number;
  offset?: number;
} = {}): string {
  const query = new URLSearchParams();
  for (const status of params.status ?? []) query.append("status", status);
  for (const priority of params.priority ?? []) query.append("priority", priority);
  if (params.board_id !== undefined) query.set("board_id", String(params.board_id));
  if (params.project_id !== undefined) query.set("project_id", String(params.project_id));
  if (params.source_kind) query.set("source_kind", params.source_kind);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  return query.toString();
}

export async function listTaskSystemTasks(params: Parameters<typeof buildTaskListQuery>[0] = {}): Promise<TaskListResponse> {
  const query = buildTaskListQuery(params);
  const url = query ? `${apiRoutes.taskSystem.tasks}?${query}` : apiRoutes.taskSystem.tasks;
  return apiFetch<TaskListResponse>(url, { cache: "no-store" });
}

export function createTaskSystemTask(body: TaskCreate): Promise<TaskItem> {
  return apiPostJson<TaskItem, TaskCreate>(apiRoutes.taskSystem.tasks, body);
}

export function updateTaskSystemTask(taskId: number, patch: TaskUpdate): Promise<TaskItem> {
  return apiPatchJson<TaskItem, TaskUpdate>(apiRoutes.taskSystem.taskById(taskId), patch);
}

export function deleteTaskSystemTask(taskId: number): Promise<unknown> {
  return apiFetch(apiRoutes.taskSystem.taskById(taskId), { method: "DELETE" });
}

export function markTaskSystemTaskDone(taskId: number, reflection_md?: string): Promise<TaskDoneResponse> {
  return apiPatchJson<TaskDoneResponse, { reflection_md?: string; award_rewards: boolean }>(
    apiRoutes.taskSystem.taskDone(taskId),
    { reflection_md, award_rewards: true },
  );
}

export function moveTaskSystemTask(taskId: number, body: TaskMoveRequest): Promise<TaskItem> {
  return apiPatchJson<TaskItem, TaskMoveRequest>(apiRoutes.taskSystem.taskMove(taskId), body);
}

export function planTaskSystemTasks(body: TaskPlanRequest): Promise<TaskPlanResponse> {
  return apiPostJson<TaskPlanResponse, TaskPlanRequest>(apiRoutes.taskSystem.plan, body);
}

export function listTaskSystemBoards(): Promise<TaskBoard[]> {
  return apiFetch<TaskBoard[]>(apiRoutes.taskSystem.boards, { cache: "no-store" });
}

export function ensureTaskSystemDefaultBoard(): Promise<TaskBoard> {
  return apiPostJson<TaskBoard, Record<string, never>>(apiRoutes.taskSystem.defaultBoard, {});
}

export function listTaskSystemColumns(boardId: number): Promise<TaskColumn[]> {
  return apiFetch<TaskColumn[]>(apiRoutes.taskSystem.boardColumns(boardId), { cache: "no-store" });
}

export function scheduleTaskSystemFocusBlock(body: TaskCalendarEventCreate): Promise<TaskCalendarEvent> {
  return apiPostJson<TaskCalendarEvent, TaskCalendarEventCreate>(apiRoutes.taskSystem.calendarEvents, body);
}

export function startTaskSystemFocusSession(body: TaskFocusSessionCreate): Promise<TaskFocusSession> {
  return apiPostJson<TaskFocusSession, TaskFocusSessionCreate>(apiRoutes.taskSystem.focusSessions, body);
}

export function completeTaskSystemFocusSession(sessionId: number, body: { ended_at?: string; interruptions?: number }): Promise<TaskFocusSession> {
  return apiPatchJson<TaskFocusSession, typeof body>(apiRoutes.taskSystem.completeFocusSession(sessionId), body);
}

export function startTaskSystemPomodoro(body: TaskFocusSessionCreate): Promise<TaskFocusSession> {
  return apiPostJson<TaskFocusSession, TaskFocusSessionCreate>(apiRoutes.taskSystem.startPomodoro, body);
}

export function completeTaskSystemPomodoro(body: TaskPomodoroCreate): Promise<TaskPomodoro> {
  return apiPostJson<TaskPomodoro, TaskPomodoroCreate>(apiRoutes.taskSystem.completePomodoro, body);
}
