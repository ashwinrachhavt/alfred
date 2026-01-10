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

export type CompanyContact = {
  name: string;
  title: string;
  email: string;
  confidence: number;
  source: string;
};

export type CompanyContactsDiscoverResponse = {
  company: string;
  role: string | null;
  limit: number;
  refresh: boolean;
  providers: string[] | null;
  items: CompanyContact[];
};

export type CompanyContactDbRow = CompanyContact & {
  id: number | null;
  run_id: number;
  created_at: string | null;
  company: string;
};

export type CompanyContactsDbResponse = {
  company: string;
  role: string | null;
  limit: number;
  providers: string[] | null;
  items: CompanyContactDbRow[];
};
