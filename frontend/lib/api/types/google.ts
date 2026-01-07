export type GoogleStatusResponse = {
  configured: boolean;
  gmail_token_present: boolean;
  calendar_token_present: boolean;
  expires_at: string | null;
  expired: boolean | null;
  scopes: string[];
};

export type GoogleAuthUrlResponse = {
  authorization_url: string;
  state: string;
};

export type GoogleRevokeResponse = {
  ok: boolean;
  removed: string[];
};

export type GmailProfileResponse = {
  email_address?: string;
  messages_total?: number;
  threads_total?: number;
  history_id?: string;
};

export type GmailMessagePreview = {
  id: string;
  thread_id?: string;
  snippet?: string;
  internal_date?: string;
  label_ids: string[];
  headers: {
    From?: string;
    To?: string;
    Subject?: string;
    Date?: string;
  };
};

export type GmailMessagesResponse = {
  items: GmailMessagePreview[];
  count: number;
  max_results: number;
};

export type GmailAttachment = {
  filename: string;
  mimeType: string;
  attachmentId?: string;
  size?: number;
};

export type GmailMessageResponse = {
  id: string;
  thread_id?: string;
  snippet?: string;
  internal_date?: string;
  label_ids: string[];
  headers: Record<string, string>;
  body: string | null;
  attachments: GmailAttachment[];
};

export type CalendarEventsResponse = {
  items: unknown[];
};
