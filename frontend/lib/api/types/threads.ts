export type Thread = {
  id: string;
  kind: string;
  title?: string | null;
  user_id?: number | null;
  metadata: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ThreadMessageRole = string;

export type ThreadMessage = {
  id: string;
  thread_id: string;
  role: ThreadMessageRole;
  content?: string | null;
  data: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type CreateThreadRequest = {
  kind: string;
  title?: string | null;
  user_id?: number | null;
  metadata?: Record<string, unknown>;
};

export type AppendThreadMessageRequest = {
  role: ThreadMessageRole;
  content?: string | null;
  data?: Record<string, unknown>;
};
