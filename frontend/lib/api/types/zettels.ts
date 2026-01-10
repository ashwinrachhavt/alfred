export type ZettelCardCreate = {
  title: string;
  content?: string | null;
  summary?: string | null;
  tags?: string[] | null;
  topic?: string | null;
  source_url?: string | null;
  document_id?: string | null;
  importance?: number;
  confidence?: number;
  status?: string;
};

export type ZettelCardPatch = {
  id: number;
  title?: string | null;
  content?: string | null;
  summary?: string | null;
  tags?: string[] | null;
  topic?: string | null;
  source_url?: string | null;
  document_id?: string | null;
  importance?: number | null;
  confidence?: number | null;
  status?: string | null;
};

export type ZettelCardOut = {
  id: number;
  title: string;
  content?: string | null;
  summary?: string | null;
  tags?: string[] | null;
  topic?: string | null;
  source_url?: string | null;
  document_id?: string | null;
  importance: number;
  confidence: number;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ZettelLinkCreate = {
  to_card_id: number;
  type?: string;
  context?: string | null;
  bidirectional?: boolean;
};

export type ZettelLinkOut = {
  id: number;
  from_card_id: number;
  to_card_id: number;
  type: string;
  context?: string | null;
  bidirectional: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

export type GraphSummary = {
  nodes: Record<string, unknown>[];
  edges: Record<string, unknown>[];
};

export type ZettelReviewOut = {
  id: number;
  card_id: number;
  stage: number;
  iteration: number;
  due_at: string;
  completed_at?: string | null;
  score?: number | null;
};

export type CompleteReviewRequest = {
  score?: number | null;
};

export type BulkUpdateResult = {
  updated_ids: number[];
  missing_ids: number[];
};

export type LinkQuality = {
  semantic_score: number;
  tag_overlap: number;
  topic_match: boolean;
  citation_overlap: number;
  temporal_proximity_days?: number | null;
  composite_score: number;
  confidence: string;
};

export type LinkSuggestion = {
  to_card_id: number;
  to_title: string;
  to_topic?: string | null;
  to_tags?: string[] | null;
  reason: string;
  scores: LinkQuality;
};

