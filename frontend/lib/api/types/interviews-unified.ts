export type UnifiedInterviewOperation =
  | "collect_questions"
  | "deep_research"
  | "practice_session";

export type UnifiedInterviewRequest = {
  operation: UnifiedInterviewOperation;
  company: string;
  role?: string;
  max_sources?: number;
  max_questions?: number;
  use_firecrawl?: boolean;
  include_deep_research?: boolean;
  target_length_words?: number;
  session_id?: string | null;
  candidate_response?: string | null;
  candidate_background?: string | null;
};

export type QuestionValidation = {
  is_valid: boolean;
  confidence: number;
  reasoning: string;
};

export type QuestionSolution = {
  approach: string;
  time_complexity?: string | null;
  space_complexity?: string | null;
  key_insights?: string[];
};

export type UnifiedQuestion = {
  question: string;
  categories?: string[];
  occurrences?: number | null;
  sources?: string[];
  validation?: QuestionValidation | null;
  solution?: QuestionSolution | null;
};

export type UnifiedInterviewResponse = {
  operation: UnifiedInterviewOperation;
  questions?: UnifiedQuestion[] | null;
  sources_scraped?: number | null;
  research_report?: string | null;
  key_insights?: string[] | null;
  session_id?: string | null;
  interviewer_response?: string | null;
  feedback?: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
};

export type EnqueueUnifiedInterviewTaskResponse = {
  task_id: string;
  status_url: string;
  status: "queued";
};

