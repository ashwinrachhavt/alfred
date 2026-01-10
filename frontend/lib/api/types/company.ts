export type CompanyResearchQueuedResponse = {
  task_id: string;
  status_url: string;
  status: string;
};

export type CompanyResearchReportSection = {
  name: string;
  summary: string;
  insights: string[];
};

export type CompanyResearchReport = {
  company: string;
  executive_summary: string;
  sections: CompanyResearchReportSection[];
  risks: string[];
  opportunities: string[];
  recommended_actions: string[];
  references: string[];
};

export type CompanyResearchSource = {
  title: string | null;
  url: string | null;
  snippet: string | null;
  markdown: string | null;
  provider: string | null;
  error?: string | null;
};

export type CompanyResearchPayload = {
  company: string;
  model?: string;
  generated_at?: string;
  report: CompanyResearchReport;
  sources: CompanyResearchSource[];
  search?: unknown;
};

export type CompanyResearchResponse = CompanyResearchPayload | CompanyResearchQueuedResponse;

export type CompanyResearchReportSummary = {
  id: string;
  company: string;
  model_name?: string | null;
  generated_at?: string | null;
  updated_at?: string | null;
  executive_summary?: string | null;
};

export type CompanyResearchReportPayloadResponse = CompanyResearchPayload & {
  id: string;
};

export type CompanyInsightsResponse = Record<string, unknown>;

export type CompanyOutreachResponse = Record<string, unknown>;

export type ContactProvider = "hunter" | "apollo" | "snov";

export type CompanyContactsResponse = Record<string, unknown>;

export type OutreachRequest = {
  name: string;
  role?: string | null;
  context?: string | null;
  k?: number | null;
};

export type OutreachSendRequest = {
  company: string;
  contact_email: string;
  contact_name?: string | null;
  contact_title?: string | null;
  subject: string;
  body: string;
  dry_run?: boolean;
};

export type OutreachSendResponse = Record<string, unknown>;
