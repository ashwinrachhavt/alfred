export type NotionHistoryPage = {
  page_id: string;
  title: string;
  last_edited_time?: string | null;
  content?: unknown;
};

export type NotionHistoryResponse = {
  success: boolean;
  count: number;
  pages: NotionHistoryPage[];
};

export type NotionPageSearchResult = {
  page_id: string;
  title: string;
  url?: string | null;
  last_edited_time?: string | null;
};

export type NotionPageSearchResponse = {
  results: NotionPageSearchResult[];
};

export type NotionPageMarkdownResponse = {
  page_id: string;
  title: string;
  url?: string | null;
  last_edited_time?: string | null;
  markdown: string;
};

export type UpdateNotionPageMarkdownRequest = {
  markdown: string;
  mode?: "replace" | "append";
};

export type UpdateNotionPageMarkdownResponse = {
  success: boolean;
  page_id: string;
  mode: "replace" | "append";
};
