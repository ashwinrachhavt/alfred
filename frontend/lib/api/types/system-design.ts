export type ExcalidrawData = {
  elements: Record<string, unknown>[];
  appState: Record<string, unknown>;
  files: Record<string, unknown>;
  metadata?: Record<string, unknown>;
};

export type SystemDesignSessionCreate = {
  title?: string | null;
  problem_statement: string;
  template_id?: string | null;
  metadata?: Record<string, unknown>;
};

export type DiagramVersion = {
  id: string;
  created_at: string;
  label?: string | null;
  diagram: ExcalidrawData;
};

export type DiagramExport = {
  id: string;
  format: string;
  created_at: string;
  storage_url?: string | null;
  notes?: string | null;
};

export type SystemDesignArtifacts = {
  learning_topic_ids: number[];
  learning_resource_ids: number[];
  zettel_card_ids: number[];
  interview_prep_id?: string | null;
  published_at?: string | null;
};

export type SystemDesignSession = {
  id: string;
  share_id: string;
  title?: string | null;
  problem_statement: string;
  template_id?: string | null;
  notes_markdown?: string | null;
  diagram: ExcalidrawData;
  versions: DiagramVersion[];
  exports: DiagramExport[];
  artifacts: SystemDesignArtifacts;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
};

export type AutosaveRequest = {
  diagram: ExcalidrawData;
  label?: string | null;
};

export type SystemDesignSessionUpdate = {
  title?: string;
  problem_statement?: string;
};

export type SystemDesignNotesUpdate = {
  notes_markdown: string;
};

export type DesignPrompt = {
  problem: string;
  constraints: string[];
  target_scale?: string | null;
};

export type InvalidConnection = {
  source: string;
  target: string;
  reason: string;
};

export type DiagramAnalysis = {
  detected_components: string[];
  missing_components: string[];
  invalid_connections: InvalidConnection[];
  bottlenecks: string[];
  best_practices_hints: string[];
  completeness_score: number;
  scale_notes: string[];
};

export type DiagramQuestion = {
  id: string;
  text: string;
  rationale?: string | null;
};

export type DiagramSuggestion = {
  id: string;
  text: string;
  priority?: string;
};

export type DiagramEvaluation = {
  completeness: number;
  scalability: number;
  tradeoffs: number;
  communication: number;
  technical_depth: number;
  notes: string[];
};

export type SystemDesignKnowledgeTopic = {
  title: string;
  description?: string | null;
  tags?: string[];
};

export type SystemDesignZettelDraft = {
  title: string;
  summary?: string | null;
  content?: string | null;
  tags?: string[];
  topic?: string | null;
};

export type SystemDesignInterviewPrepDraft = {
  likely_questions: Array<{
    question: string;
    suggested_answer: string;
    focus_areas?: string[];
  }>;
  technical_topics: Array<{
    topic: string;
    priority?: number;
    notes?: string | null;
    resources?: string[];
  }>;
};

export type SystemDesignKnowledgeDraft = {
  topics: SystemDesignKnowledgeTopic[];
  zettels: SystemDesignZettelDraft[];
  interview_prep: SystemDesignInterviewPrepDraft;
  notes: string[];
};

export type SystemDesignPublishRequest = {
  create_learning_topics?: boolean;
  create_zettels?: boolean;
  create_interview_prep_items?: boolean;
  learning_topic_id?: number | null;
  interview_prep_id?: string | null;
  topic_title?: string | null;
  topic_tags?: string[];
  zettel_tags?: string[];
};

export type SystemDesignPublishResponse = {
  session: SystemDesignSession;
  artifacts: SystemDesignArtifacts;
  knowledge_draft: SystemDesignKnowledgeDraft;
};

export type ScaleEstimateRequest = {
  qps: number;
  avg_request_kb: number;
  avg_response_kb: number;
  write_percentage?: number;
  storage_per_write_kb?: number;
  retention_days?: number;
  replication_factor?: number;
};

export type ScaleEstimateResponse = {
  inbound_mbps: number;
  outbound_mbps: number;
  writes_per_day: number;
  storage_gb_per_day: number;
  retained_storage_gb: number;
};

export type ComponentDefinition = {
  id: string;
  name: string;
  category: string;
  description: string;
  default_element: Record<string, unknown>;
};

export type TemplateDefinition = {
  id: string;
  name: string;
  description: string;
  components: string[];
  diagram: ExcalidrawData;
};
