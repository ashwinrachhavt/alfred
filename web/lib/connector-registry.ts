import {
  BookOpen, FileText, Github, Globe, Highlighter,
  Newspaper, Notebook, Rss, type LucideIcon,
} from "lucide-react";

export type ConnectorDef = {
  key: string;
  label: string;
  icon: LucideIcon;
  contentType: string;
  statusEndpointName: string;
};

export const connectors: ConnectorDef[] = [
  { key: "web", label: "Articles", icon: Globe, contentType: "web", statusEndpointName: "web" },
  { key: "readwise", label: "Highlights", icon: Highlighter, contentType: "highlight", statusEndpointName: "readwise" },
  { key: "notion", label: "Notes", icon: Notebook, contentType: "notion", statusEndpointName: "notion" },
  { key: "arxiv", label: "Papers", icon: FileText, contentType: "paper", statusEndpointName: "arxiv" },
  { key: "github", label: "GitHub", icon: Github, contentType: "github", statusEndpointName: "github/import" },
  { key: "rss", label: "RSS", icon: Rss, contentType: "rss", statusEndpointName: "rss" },
  { key: "hypothesis", label: "Annotations", icon: BookOpen, contentType: "annotation", statusEndpointName: "hypothesis" },
  { key: "pocket", label: "Pocket", icon: Newspaper, contentType: "pocket", statusEndpointName: "pocket" },
];
