export type WritingPreset = {
  key: string;
  title: string;
  description?: string;
  max_chars?: number | null;
  format?: "plain" | "markdown";
};

export type WritingRequest = {
  intent?: "compose" | "rewrite" | "reply" | "edit";
  thread_id?: string | null;
  site_url?: string;
  preset?: string | null;
  instruction?: string;
  draft?: string;
  selection?: string;
  page_title?: string;
  page_text?: string;
  temperature?: number | null;
  max_chars?: number | null;
};

export type WritingResponse = {
  preset_used: WritingPreset;
  output: string;
};

