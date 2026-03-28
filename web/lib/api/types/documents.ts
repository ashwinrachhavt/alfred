export type ExplorerDocumentItem = {
  id: string;
  title: string;
  cover_image_url?: string | null;
  summary?: string | null;
  created_at: string;
  day_bucket: string;
  primary_topic?: string | null;
  source_url?: string | null;
  canonical_url?: string | null;
  classification?: {
    domain?: { slug: string; display: string };
    subdomain?: { slug: string; display: string };
    microtopics?: Array<{ slug: string; display: string }>;
    topic?: { title: string; confidence: number };
  } | null;
};

export type ExplorerDocumentsResponse = {
  items: ExplorerDocumentItem[];
  next_cursor?: string | null;
  limit: number;
  filter_topic?: string | null;
  search?: string | null;
};

export type SemanticMapPoint = {
  id: string;
  pos: [number, number, number];
  color: string;
  label: string;
  primary_topic?: string | null;
};

export type SemanticMapResponse = {
  points: SemanticMapPoint[];
};

export type DocumentDetailsResponse = {
  id: string;
  source_url: string;
  canonical_url?: string | null;
  domain?: string | null;
  title?: string | null;
  cover_image_url?: string | null;
  content_type: string;
  lang?: string | null;
  raw_markdown?: string | null;
  cleaned_text: string;
  tokens?: number | null;
  summary?: Record<string, unknown> | null;
  topics?: Record<string, unknown> | null;
  entities?: Record<string, unknown> | null;
  tags: string[];
  captured_at: string;
  day_bucket: string;
  created_at: string;
  updated_at: string;
  session_id?: string | null;
  metadata: Record<string, unknown>;
  enrichment?: Record<string, unknown> | null;
};
