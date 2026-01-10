export type ToolsStatusResponse = Record<string, unknown>;

export type SlackSendRequest = {
  channel: string;
  text: string;
  thread_ts?: string | null;
};

export type SlackSendResponse = Record<string, unknown>;

export type StoreQueryRequest = {
  collection: string;
  filter?: Record<string, unknown> | null;
  limit?: number;
};

export type StoreQueryResponse = Record<string, unknown>;

