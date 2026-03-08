export type Workspace = {
  id: string;
  name: string;
  icon: string | null;
  user_id: number | null;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type WorkspaceCreateRequest = {
  name: string;
  icon?: string | null;
  settings?: Record<string, unknown> | null;
};

export type NoteSummary = {
  id: string;
  title: string;
  icon: string | null;
  cover_image: string | null;
  parent_id: string | null;
  workspace_id: string;
  position: number;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
};

export type NoteResponse = NoteSummary & {
  content_markdown: string;
  content_json: Record<string, unknown> | null;
  created_by: number | null;
  last_edited_by: number | null;
};

export type NoteCreateRequest = {
  title?: string | null;
  icon?: string | null;
  cover_image?: string | null;
  parent_id?: string | null;
  workspace_id?: string | null;
  content_markdown?: string | null;
  content_json?: Record<string, unknown> | null;
};

export type NoteUpdateRequest = {
  title?: string | null;
  icon?: string | null;
  cover_image?: string | null;
  content_markdown?: string | null;
  content_json?: Record<string, unknown> | null;
  is_archived?: boolean | null;
};

export type NotesListResponse = {
  items: NoteSummary[];
  total: number;
  skip: number;
  limit: number;
};

export type NoteTreeNode = {
  note: NoteSummary;
  children: NoteTreeNode[];
};

export type NoteTreeResponse = {
  workspace_id: string;
  items: NoteTreeNode[];
};

export type NoteAssetResponse = {
  id: string;
  note_id: string;
  workspace_id: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  sha256: string | null;
  url: string;
  created_at: string;
  created_by: number | null;
};

