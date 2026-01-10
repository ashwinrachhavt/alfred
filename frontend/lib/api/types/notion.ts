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

