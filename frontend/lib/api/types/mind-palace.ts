export type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

export type AgentQueryRequest = {
  question: string;
  history?: ChatMessage[];
  context?: Record<string, unknown>;
};

export type AgentResponse = {
  answer: string;
  sources?: Record<string, unknown>[] | null;
  meta?: Record<string, unknown>;
};

export type EnqueueMindPalaceTaskResponse = {
  task_id: string;
  status_url: string;
};

export type MindPalaceQueryResponse = AgentResponse | EnqueueMindPalaceTaskResponse;

