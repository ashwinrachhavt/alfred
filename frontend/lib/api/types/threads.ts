export type Thread = {
  id: string;
  title?: string | null;
  created_at?: string;
  updated_at?: string | null;
};

export type ThreadMessageRole = string;

export type ThreadMessage = {
  id: string;
  thread_id: string;
  role: ThreadMessageRole;
  content: string;
  created_at?: string;
  metadata?: Record<string, unknown> | null;
};

export type CreateThreadRequest = {
  title?: string | null;
};

export type AppendThreadMessageRequest = {
  role: ThreadMessageRole;
  content: string;
  metadata?: Record<string, unknown> | null;
};
