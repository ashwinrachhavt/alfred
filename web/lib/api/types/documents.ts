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
  pipeline_status?: string;
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
  total_count?: number;
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

export type SourceCaptureHeading = {
  level: number;
  text: string;
};

export type SourceCaptureImage = {
  url: string;
  local_url?: string;
  alt?: string;
  position?: number;
};

export type SourceCaptureLink = {
  url: string;
  text?: string;
  position?: number;
};

export type SourceCapture = {
  kind?: string | null;
  platform?: string | null;
  title?: string | null;
  subtitle?: string | null;
  author?: string | null;
  published_at?: string | null;
  canonical_url?: string | null;
  cover_image_url?: string | null;
  headings?: SourceCaptureHeading[];
  images?: SourceCaptureImage[];
  links?: SourceCaptureLink[];
  firecrawl?: Record<string, unknown>;
};

export type SourceAnalysis = {
  kind?: string | null;
  platform?: string | null;
  author?: string | null;
  thesis?: string | null;
  argument_flow?: string[];
  audience?: string | null;
  structure?: string[];
};

export type DocumentMetadata = Record<string, unknown> & {
  source_capture?: SourceCapture;
  capture?: {
    source?: string;
    mode?: string;
    rich_capture_status?: string;
    local_quality?: string;
  };
};

export type DocumentEnrichment = Record<string, unknown> & {
  source_analysis?: SourceAnalysis;
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
  metadata: DocumentMetadata;
  enrichment?: DocumentEnrichment | null;
};
