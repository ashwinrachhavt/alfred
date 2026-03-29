export type ThinkingBlock = {
  id: string;
  type:
    | "freeform"
    | "demolition"
    | "framework"
    | "anchor"
    | "law"
    | "prediction"
    | "connection"
    | "insight";
  content: string;
  meta: Record<string, unknown>;
  order: number;
};

export type ThinkingSession = {
  id: number;
  title: string | null;
  status: "draft" | "published" | "archived";
  blocks: ThinkingBlock[];
  tags: string[];
  topic: string | null;
  source_input: Record<string, unknown> | null;
  pinned: boolean;
  created_at: string;
  updated_at: string;
};

export type ThinkingSessionSummary = {
  id: number;
  title: string | null;
  status: "draft" | "published" | "archived";
  topic: string | null;
  pinned: boolean;
  tags: string[];
  block_count: number;
  created_at: string;
  updated_at: string;
};

export type DecomposeResponse = {
  blocks: ThinkingBlock[];
};
