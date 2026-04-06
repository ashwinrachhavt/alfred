/**
 * Canonical frontend API routes.
 *
 * The frontend always calls `/api/*` and relies on Next.js rewrites to reach the
 * correct backend prefix (some FastAPI routers are mounted outside `/api/*`).
 */
export const apiRoutes = {
  research: {
    deepResearch: "/api/research/",
    reportsRecent: "/api/research/reports/recent",
    reportById: (reportId: string) => `/api/research/reports/${reportId}`,
  },
  documents: {
    explorer: "/api/documents/explorer",
    search: "/api/documents/search",
    semanticMap: "/api/documents/semantic-map",
    documentDetails: (id: string) => `/api/documents/${id}/details`,
    documentText: (id: string) => `/api/documents/${id}/text`,
    documentImage: (id: string) => `/api/documents/${id}/image`,
    documentImageAsync: (id: string) => `/api/documents/${id}/image/async`,
    enrich: (id: string) => `/api/documents/doc/${id}/enrich`,
    fetchAndOrganize: (id: string) => `/api/documents/doc/${id}/fetch-and-organize`,
    pageExtract: "/api/documents/page/extract",
  },
  tasks: {
    status: (taskId: string) => `/api/tasks/${taskId}`,
  },
  intelligence: {
    autocomplete: "/api/intelligence/autocomplete",
    edit: "/api/intelligence/edit",
    qa: "/api/intelligence/qa",
    summarizeText: "/api/intelligence/summarize/text",
    summarizeUrl: "/api/intelligence/summarize/url",
    summarizePdf: "/api/intelligence/summarize/pdf",
    memory: "/api/intelligence/memory",
    languageDetect: "/api/intelligence/language/detect",
  },
  notes: {
    workspaces: "/api/v1/workspaces",
    createWorkspace: "/api/v1/workspaces",
    tree: "/api/v1/notes/tree",
    createNote: "/api/v1/notes",
    noteById: (noteId: string) => `/api/v1/notes/${noteId}`,
    noteAssets: (noteId: string) => `/api/v1/notes/${noteId}/assets`,
    noteAssetById: (assetId: string) => `/api/v1/notes/assets/${assetId}`,
  },
  rag: {
    answer: "/api/rag/answer",
  },
  zettels: {
    cards: "/api/zettels/cards",
    cardById: (id: number) => `/api/zettels/cards/${id}`,
    cardLinks: (id: number) => `/api/zettels/cards/${id}/links`,
    suggestLinks: (id: number) => `/api/zettels/cards/${id}/suggest-links`,
    deleteLink: (id: number) => `/api/zettels/links/${id}`,
    generate: "/api/zettels/cards/generate",
    suggestTags: "/api/zettels/suggest-tags",
    graph: "/api/zettels/graph",
    batchLink: "/api/zettels/batch-link",
    generateLinks: (id: number) => `/api/zettels/cards/${id}/generate-links`,
    reviewsDue: "/api/zettels/reviews/due",
    topics: "/api/zettels/topics",
    tags: "/api/zettels/tags",
  },
  pipeline: {
    replay: (docId: string) => `/api/pipeline/${docId}/replay`,
    status: (docId: string) => `/api/pipeline/${docId}/status`,
    replayBatch: "/api/pipeline/replay-batch",
  },
  whiteboards: {
    list: "/api/whiteboards",
    create: "/api/whiteboards",
    byId: (id: number) => `/api/whiteboards/${id}`,
    revisions: (id: number) => `/api/whiteboards/${id}/revisions`,
  },
  canvas: {
    generateDiagram: "/api/canvas/generate-diagram",
  },
  learning: {
    topics: "/api/learning/topics",
    graph: "/api/learning/graph",
    retentionMetrics: "/api/learning/metrics/retention",
    reviewsDue: "/api/learning/reviews/due",
    gaps: "/api/learning/gaps",
  },
  writing: {
    compose: "/api/writing/compose",
    composeStream: "/api/writing/compose/stream",
    presets: "/api/writing/presets",
  },
  mindPalace: {
    query: "/api/mind-palace/agent/query",
  },
  agent: {
    stream: "/api/agent/stream",
    threads: "/api/agent/threads",
    threadById: (id: number) => `/api/agent/threads/${id}`,
  },
  connectors: {
    status: (name: string) => `/api/${name}/status`,
    statusAll: "/api/connectors/status-all",
  },
  thinking: {
    sessions: "/api/thinking/sessions",
    sessionById: (id: number) => `/api/thinking/sessions/${id}`,
    archive: (id: number) => `/api/thinking/sessions/${id}/archive`,
    fork: (id: number) => `/api/thinking/sessions/${id}/fork`,
    decompose: "/api/thinking/decompose",
  },
  dictionary: {
    lookup: "/api/dictionary/lookup",
    entries: "/api/dictionary/entries",
    entryById: (id: number) => `/api/dictionary/entries/${id}`,
    search: "/api/dictionary/search",
    regenerateAi: (id: number) => `/api/dictionary/entries/${id}/regenerate-ai`,
  },
  taxonomy: {
    domains: "/api/taxonomy/domains",
    tree: "/api/taxonomy/tree",
    reclassifyAll: "/api/taxonomy/reclassify-all",
    nodes: "/api/taxonomy/nodes",
    nodeBySlug: (slug: string) => `/api/taxonomy/nodes/${slug}`,
  },
  capture: {
    ingest: "/api/capture",
  },
  today: {
    briefing: "/api/today/briefing",
  },
} as const;
