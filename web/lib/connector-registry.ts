import {
  BookOpen, Brain, FileText, Github, Globe,
  Highlighter, Mail, Calendar, HardDrive, CheckSquare,
  Newspaper, Notebook, Rss, Search, MessageSquare,
  ListTodo, Table2, Zap, type LucideIcon,
} from "lucide-react";

export type ConnectorCategory = "knowledge" | "productivity" | "ai";
export type ConnectorAuthType = "oauth" | "api_key" | "none";

export type ConnectorDef = {
  key: string;
  label: string;
  icon: LucideIcon;
  description: string;
  category: ConnectorCategory;
  authType: ConnectorAuthType;
  contentType: string;
  statusEndpoint: string;
  hasBackend: boolean;
};

export const connectors: ConnectorDef[] = [
  // ── Knowledge Sources ────────────────────────────────
  { key: "notion", label: "Notion", icon: Notebook, description: "Sync pages and databases from Notion workspaces", category: "knowledge", authType: "oauth", contentType: "notion", statusEndpoint: "notion", hasBackend: true },
  { key: "readwise", label: "Readwise", icon: Highlighter, description: "Import highlights and annotations from Readwise", category: "knowledge", authType: "api_key", contentType: "highlight", statusEndpoint: "readwise", hasBackend: true },
  { key: "pocket", label: "Pocket", icon: Newspaper, description: "Saved articles and bookmarks from Pocket", category: "knowledge", authType: "api_key", contentType: "pocket", statusEndpoint: "pocket", hasBackend: true },
  { key: "hypothesis", label: "Hypothesis", icon: BookOpen, description: "Web annotations and highlights", category: "knowledge", authType: "api_key", contentType: "annotation", statusEndpoint: "hypothesis", hasBackend: true },
  { key: "arxiv", label: "ArXiv", icon: FileText, description: "Academic papers from ArXiv", category: "knowledge", authType: "none", contentType: "paper", statusEndpoint: "arxiv_import", hasBackend: true },
  { key: "semantic_scholar", label: "Semantic Scholar", icon: Search, description: "Academic paper search and citations", category: "knowledge", authType: "api_key", contentType: "paper", statusEndpoint: "semantic_scholar", hasBackend: true },
  { key: "wikipedia", label: "Wikipedia", icon: Globe, description: "Encyclopedia knowledge lookup", category: "knowledge", authType: "none", contentType: "web", statusEndpoint: "wikipedia", hasBackend: true },
  { key: "rss", label: "RSS", icon: Rss, description: "Subscribe to RSS and Atom feeds", category: "knowledge", authType: "none", contentType: "rss", statusEndpoint: "rss", hasBackend: true },
  { key: "web", label: "Web", icon: Globe, description: "Scrape and ingest web pages via Firecrawl", category: "knowledge", authType: "api_key", contentType: "web", statusEndpoint: "web", hasBackend: true },

  // ── Productivity ─────────────────────────────────────
  { key: "gmail", label: "Gmail", icon: Mail, description: "Email messages and threads from Gmail", category: "productivity", authType: "oauth", contentType: "email", statusEndpoint: "gmail", hasBackend: true },
  { key: "calendar", label: "Google Calendar", icon: Calendar, description: "Events and schedules from Google Calendar", category: "productivity", authType: "oauth", contentType: "calendar", statusEndpoint: "calendar", hasBackend: true },
  { key: "gdrive", label: "Google Drive", icon: HardDrive, description: "Documents and files from Google Drive", category: "productivity", authType: "oauth", contentType: "drive", statusEndpoint: "gdrive", hasBackend: true },
  { key: "google_tasks", label: "Google Tasks", icon: CheckSquare, description: "Task lists from Google Tasks", category: "productivity", authType: "oauth", contentType: "tasks", statusEndpoint: "google_tasks", hasBackend: true },
  { key: "github", label: "GitHub", icon: Github, description: "Repositories, issues, and activity from GitHub", category: "productivity", authType: "api_key", contentType: "github", statusEndpoint: "github/import", hasBackend: true },
  { key: "linear", label: "Linear", icon: Zap, description: "Issues and projects from Linear", category: "productivity", authType: "api_key", contentType: "linear", statusEndpoint: "linear", hasBackend: true },
  { key: "todoist", label: "Todoist", icon: ListTodo, description: "Tasks and projects from Todoist", category: "productivity", authType: "api_key", contentType: "todoist", statusEndpoint: "todoist", hasBackend: true },
  { key: "airtable", label: "Airtable", icon: Table2, description: "Records and bases from Airtable", category: "productivity", authType: "api_key", contentType: "airtable", statusEndpoint: "airtable", hasBackend: true },
  { key: "slack", label: "Slack", icon: MessageSquare, description: "Messages and channels from Slack", category: "productivity", authType: "api_key", contentType: "slack", statusEndpoint: "slack", hasBackend: true },

  // ── AI & Search ──────────────────────────────────────
  { key: "searxng", label: "SearxNG", icon: Search, description: "Local metasearch engine (self-hosted)", category: "ai", authType: "none", contentType: "search", statusEndpoint: "searxng", hasBackend: false },
  { key: "tavily", label: "Tavily", icon: Search, description: "AI-optimized web search for agents", category: "ai", authType: "api_key", contentType: "search", statusEndpoint: "tavily", hasBackend: false },
  { key: "brave_search", label: "Brave Search", icon: Globe, description: "Privacy-first independent web search", category: "ai", authType: "api_key", contentType: "search", statusEndpoint: "brave_search", hasBackend: false },
  { key: "wolfram", label: "Wolfram Alpha", icon: Brain, description: "Computational knowledge engine", category: "ai", authType: "api_key", contentType: "compute", statusEndpoint: "wolfram", hasBackend: false },
  { key: "exa", label: "Exa.ai", icon: Zap, description: "Neural search engine for LLM workflows", category: "ai", authType: "api_key", contentType: "search", statusEndpoint: "exa", hasBackend: false },
];

export const connectorsByCategory = {
  knowledge: connectors.filter((c) => c.category === "knowledge"),
  productivity: connectors.filter((c) => c.category === "productivity"),
  ai: connectors.filter((c) => c.category === "ai"),
} as const;

export const categoryLabels: Record<ConnectorCategory, string> = {
  knowledge: "Knowledge Sources",
  productivity: "Productivity",
  ai: "AI & Search Engines",
};

export function getConnector(key: string): ConnectorDef | undefined {
  return connectors.find((c) => c.key === key);
}
