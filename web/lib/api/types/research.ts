export type ResearchQueuedResponse = {
  task_id: string;
  status_url: string;
  status: string;
};

export type ResearchReportSection = {
  name: string;
  summary: string;
  insights: string[];
};

export type ResearchReport = {
  company?: string;
  topic?: string;
  executive_summary: string;
  sections: ResearchReportSection[];
  risks: string[];
  opportunities: string[];
  recommended_actions: string[];
  references: string[];
};

export type ResearchSource = {
  title: string | null;
  url: string | null;
  snippet: string | null;
  markdown: string | null;
  provider: string | null;
  error?: string | null;
};

export type ResearchPayload = {
  topic?: string;
  company?: string;
  model?: string;
  generated_at?: string;
  report: ResearchReport;
  sources: ResearchSource[];
  search?: unknown;
};

export type ResearchResponse = ResearchPayload | ResearchQueuedResponse;

export type ResearchReportSummary = {
  id: string;
  topic?: string;
  company?: string;
  model_name?: string | null;
  generated_at?: string | null;
  updated_at?: string | null;
  executive_summary?: string | null;
};

export type ResearchReportPayloadResponse = ResearchPayload & {
  id: string;
};
