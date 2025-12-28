export type TaskStatusResponse = {
  task_id: string;
  status: string;
  ready: boolean;
  successful: boolean;
  failed: boolean;
  result?: unknown | null;
  error?: string | null;
};

