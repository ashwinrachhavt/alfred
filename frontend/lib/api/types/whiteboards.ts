export type WhiteboardCreate = {
  title: string;
  description?: string | null;
  created_by?: string | null;
  org_id?: string | null;
  template_id?: string | null;
  initial_scene?: Record<string, unknown> | null;
  ai_context?: Record<string, unknown> | null;
  applied_prompt?: string | null;
};

export type WhiteboardUpdate = {
  title?: string | null;
  description?: string | null;
  template_id?: string | null;
  is_archived?: boolean | null;
};

export type WhiteboardWithRevision = {
  id: number;
  title: string;
  description?: string | null;
  created_by?: string | null;
  org_id?: string | null;
  template_id?: string | null;
  is_archived: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  latest_revision?: WhiteboardRevisionOut | null;
};

export type WhiteboardRevisionCreate = {
  scene_json?: Record<string, unknown>;
  ai_context?: Record<string, unknown> | null;
  applied_prompt?: string | null;
  created_by?: string | null;
};

export type WhiteboardRevisionOut = {
  id: number;
  whiteboard_id: number;
  revision_no: number;
  scene_json: Record<string, unknown>;
  ai_context?: Record<string, unknown> | null;
  applied_prompt?: string | null;
  created_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type WhiteboardCommentCreate = {
  body: string;
  element_id?: string | null;
  author?: string | null;
};

export type WhiteboardCommentOut = {
  id: number;
  whiteboard_id: number;
  element_id?: string | null;
  body: string;
  author?: string | null;
  resolved: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

