export type CompanyResearchQueuedResponse = {
  task_id: string
  status_url: string
  status: string
}

export type CompanyResearchReportSection = {
  name: string
  summary: string
  insights: string[]
}

export type CompanyResearchReport = {
  company: string
  executive_summary: string
  sections: CompanyResearchReportSection[]
  risks: string[]
  opportunities: string[]
  recommended_actions: string[]
  references: string[]
}

export type CompanyResearchSource = {
  title: string | null
  url: string | null
  snippet: string | null
  markdown: string | null
  provider: string | null
  error?: string | null
}

export type CompanyResearchPayload = {
  company: string
  model?: string
  generated_at?: string
  report: CompanyResearchReport
  sources: CompanyResearchSource[]
  search?: unknown
}

export type CompanyResearchResponse = CompanyResearchPayload | CompanyResearchQueuedResponse

