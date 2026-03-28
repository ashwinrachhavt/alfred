# Alfred Frontend Revamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Alfred frontend around four pillars — Inbox, Canvas, AI Panel, Dashboard — with a hub-and-spoke navigation model centered on a Knowledge Inbox.

**Architecture:** New app shell with top-bar navigation (replacing sidebar). AI panel as persistent right-side collapsible. Tools open as slide-over panels. Existing API client, queries/mutations, and shadcn components are preserved and reused.

**Tech Stack:** Next.js 16, React 19, Tailwind 4, shadcn/ui, TanStack Query, @xyflow/react, Tiptap, Zustand, Clerk auth, recharts

**Spec:** `docs/superpowers/specs/2026-03-20-frontend-revamp-design.md`

**Task Order & Dependencies:**
- Task 1 (Stores) → no deps
- Task 2 (API Routes) → no deps
- Task 3 (Navigation) → no deps
- Task 4 (App Shell) → depends on Tasks 1, 3. **IMPORTANT:** Task 4 Step 7 (providers cleanup) removes `AssistantProvider`/`AssistantSheet` imports. The command palette (`app-command-palette.tsx`) imports `useAssistant` from `assistant-sheet`. You MUST update the command palette (Task 8) in the SAME commit as the providers cleanup, or the build will break. Recommended: execute Task 8 Step 2 immediately after Task 4 Step 7, before running Step 8 (verify).
- Task 5 (Inbox) → depends on Tasks 2, 4
- Task 6 (Dashboard) → depends on Tasks 2, 4
- Task 7 (Canvas) → depends on Tasks 1, 2, 4
- Task 8 (Command Palette) → execute alongside Task 4 (see note above)
- Task 9 (Cleanup) → depends on all above
- Task 10 (Smoke Test) → depends on all above

**Intentional deferrals (scaffolded now, enhanced later):**
- Dashboard recharts visualizations (decay curves, treemap, mini graph) — current cards show text metrics. Charts can be added incrementally without changing the architecture.
- Responsive/mobile layout — desktop-first. Mobile bottom tab bar, full-screen sheets per spec to be added in a follow-up pass.
- Inbox quick-action buttons with task polling — the InboxItem scaffold shows stage badges but the Decompose/Connect/Review action buttons require the backend `content_type` and `stage` filter extensions first.
- Canvas-to-Inbox drag-and-drop — requires cross-page state coordination, deferred.
- `activeTab` source filtering — requires backend `content_type` filter (noted in spec as Backend Gap).

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `web/lib/stores/shell-store.ts` | Zustand store: AI panel open/close, tool panel state |
| `web/lib/stores/ai-panel-store.ts` | Zustand store: AI chat messages, streaming state, context |
| `web/lib/stores/canvas-store.ts` | Zustand store: active canvas, view filter, AI suggest toggle |
| `web/app/(app)/_components/app-shell.tsx` | New shell: top bar + AI panel + tool panel slots |
| `web/app/(app)/_components/top-bar.tsx` | Top navigation bar with 4 pillar links |
| `web/app/(app)/_components/ai-panel.tsx` | Persistent AI chat panel (Cmd-J) |
| `web/app/(app)/_components/tool-panel.tsx` | Generic slide-over container for tools |
| `web/app/(app)/inbox/page.tsx` | Knowledge Inbox page |
| `web/app/(app)/inbox/_components/inbox-stream.tsx` | Infinite scroll document stream |
| `web/app/(app)/inbox/_components/inbox-filters.tsx` | Source tabs + filter bar |
| `web/app/(app)/inbox/_components/inbox-item.tsx` | Single stream item card |
| `web/app/(app)/inbox/_components/inbox-detail.tsx` | Expanded item detail slide-over |
| `web/lib/connector-registry.ts` | Maps connector names to labels, icons, content_types |
| `web/app/(app)/canvas/page.tsx` | Default canvas (redirect to most recent) |
| `web/app/(app)/canvas/[canvasId]/page.tsx` | Specific canvas page |
| `web/app/(app)/canvas/_components/canvas-workspace.tsx` | @xyflow/react container |
| `web/app/(app)/canvas/_components/canvas-toolbar.tsx` | Canvas top toolbar |
| `web/app/(app)/canvas/_components/canvas-selector.tsx` | Canvas picker dropdown |
| `web/app/(app)/canvas/_components/canvas-node-document.tsx` | Custom xyflow node: document |
| `web/app/(app)/canvas/_components/canvas-node-zettel.tsx` | Custom xyflow node: zettel |
| `web/app/(app)/canvas/_components/canvas-edge.tsx` | Custom edge (solid + dashed) |
| `web/app/(app)/dashboard/_components/knowledge-score.tsx` | Hero score display |
| `web/app/(app)/dashboard/_components/retention-card.tsx` | Retention metrics card |
| `web/app/(app)/dashboard/_components/coverage-card.tsx` | Topic heatmap card |
| `web/app/(app)/dashboard/_components/connections-card.tsx` | Graph metrics card |
| `web/app/(app)/dashboard/_components/activity-strip.tsx` | 7-day sparkline |

### Modified Files
| File | Changes |
|------|---------|
| `web/lib/api/routes.ts` | Add rag, zettels, pipeline, whiteboards, connectors, summarize entries |
| `web/lib/navigation.ts` | Replace nav items with 4 pillars |
| `web/app/page.tsx` | Redirect authenticated users to `/inbox` instead of `/dashboard` |
| `web/app/(app)/layout.tsx` | Use new AppShell instead of old sidebar-based shell |
| `web/app/providers.tsx` | Remove AssistantProvider/AssistantSheet (replaced by AI panel in shell) |
| `web/app/(app)/dashboard/page.tsx` | New dashboard layout with 4 metric cards |
| `web/components/app-command-palette.tsx` | Update nav targets, add tool panel triggers |
| `web/package.json` | Add `@xyflow/react` dependency |

### Preserved (no changes)
- `web/lib/api/client.ts` — API fetch utilities
- `web/lib/api/documents.ts`, `web/lib/api/types/*` — existing API functions and types
- `web/features/documents/queries.ts`, `web/features/documents/mutations.ts`
- `web/features/tasks/task-tracker-provider.tsx`, `web/features/tasks/task-tracker.ts`
- `web/components/ui/*` — all shadcn primitives
- `web/components/editor/markdown-notes-editor.tsx` — Tiptap editor
- `web/components/system-design/*` — Excalidraw canvas
- `web/middleware.ts` — Clerk auth middleware
- `web/next.config.js` — API rewrites
- `web/hooks/*` — utility hooks
- `web/app/(canvas)/*` — System Design full-screen routes

---

## Task 1: Zustand Stores

**Files:**
- Create: `web/lib/stores/shell-store.ts`
- Create: `web/lib/stores/ai-panel-store.ts`
- Create: `web/lib/stores/canvas-store.ts`

- [ ] **Step 1: Create shell store**

```ts
// web/lib/stores/shell-store.ts
import { create } from "zustand";

export type ToolPanelType = "notes" | "document" | "connectors" | "quiz" | "writing";

type ToolPanel = {
  type: ToolPanelType;
  props: Record<string, unknown>;
};

type ShellState = {
  aiPanelOpen: boolean;
  toolPanel: ToolPanel | null;
  toggleAiPanel: () => void;
  openToolPanel: (type: ToolPanelType, props?: Record<string, unknown>) => void;
  closeToolPanel: () => void;
};

export const useShellStore = create<ShellState>((set) => ({
  aiPanelOpen: false,
  toolPanel: null,
  toggleAiPanel: () => set((s) => ({ aiPanelOpen: !s.aiPanelOpen })),
  openToolPanel: (type, props = {}) => set({ toolPanel: { type, props } }),
  closeToolPanel: () => set({ toolPanel: null }),
}));
```

- [ ] **Step 2: Create AI panel store**

```ts
// web/lib/stores/ai-panel-store.ts
import { create } from "zustand";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

type Message = {
  role: "user" | "assistant";
  content: string;
  citations?: string[];
};

type AiContext = {
  page: string;
  entityId?: string;
};

type AiPanelState = {
  messages: Message[];
  isStreaming: boolean;
  context: AiContext;
  sendMessage: (text: string) => Promise<void>;
  clearHistory: () => void;
  setContext: (ctx: AiContext) => void;
};

export const useAiPanelStore = create<AiPanelState>((set, get) => ({
  messages: [],
  isStreaming: false,
  context: { page: "inbox" },

  sendMessage: async (text: string) => {
    const userMsg: Message = { role: "user", content: text };
    set((s) => ({ messages: [...s.messages, userMsg], isStreaming: true }));

    try {
      const data = await apiFetch<{ answer: string }>(apiRoutes.rag.answer + "?" + new URLSearchParams({ q: text }));
      const assistantMsg: Message = { role: "assistant", content: data.answer };
      set((s) => ({ messages: [...s.messages, assistantMsg], isStreaming: false }));
    } catch {
      const errorMsg: Message = { role: "assistant", content: "Sorry, something went wrong. Please try again." };
      set((s) => ({ messages: [...s.messages, errorMsg], isStreaming: false }));
    }
  },

  clearHistory: () => set({ messages: [] }),
  setContext: (ctx) => set({ context: ctx }),
}));
```

- [ ] **Step 3: Create canvas store**

```ts
// web/lib/stores/canvas-store.ts
import { create } from "zustand";

type ViewFilter = "all" | "documents" | "concepts" | "zettels";

type CanvasState = {
  activeCanvasId: string | null;
  aiSuggestEnabled: boolean;
  selectedNodeIds: string[];
  viewFilter: ViewFilter;
  setActiveCanvas: (id: string) => void;
  toggleAiSuggest: () => void;
  setViewFilter: (f: ViewFilter) => void;
  selectNodes: (ids: string[]) => void;
};

export const useCanvasStore = create<CanvasState>((set) => ({
  activeCanvasId: null,
  aiSuggestEnabled: false,
  selectedNodeIds: [],
  viewFilter: "all",
  setActiveCanvas: (id) => set({ activeCanvasId: id }),
  toggleAiSuggest: () => set((s) => ({ aiSuggestEnabled: !s.aiSuggestEnabled })),
  setViewFilter: (f) => set({ viewFilter: f }),
  selectNodes: (ids) => set({ selectedNodeIds: ids }),
}));
```

- [ ] **Step 4: Commit**

```bash
git add web/lib/stores/
git commit -m "feat(web): add Zustand stores for shell, AI panel, and canvas state"
```

---

## Task 2: API Routes Extension

**Files:**
- Modify: `web/lib/api/routes.ts`

- [ ] **Step 1: Add all missing route entries**

Add these entries to the existing `apiRoutes` object in `web/lib/api/routes.ts`:

```ts
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
    graph: "/api/zettels/graph",
    reviewsDue: "/api/zettels/reviews/due",
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
  connectors: {
    status: (name: string) => `/api/${name}/status`,
  },
} as const;
```

- [ ] **Step 2: Commit**

```bash
git add web/lib/api/routes.ts
git commit -m "feat(web): extend apiRoutes with rag, zettels, pipeline, whiteboards, learning, writing endpoints"
```

---

## Task 3: Navigation & Connector Registry

**Files:**
- Modify: `web/lib/navigation.ts`
- Create: `web/lib/connector-registry.ts`

- [ ] **Step 1: Replace navigation with 4 pillars**

Rewrite `web/lib/navigation.ts`:

```ts
import { Brain, Inbox, LayoutDashboard, Network, type LucideIcon } from "lucide-react";

export type PillarKey = "inbox" | "canvas" | "ai" | "dashboard";

export type PillarItem = {
  key: PillarKey;
  title: string;
  href: string;
  icon: LucideIcon;
  shortcut: string; // e.g. "1" for Cmd-1
};

export const pillars: PillarItem[] = [
  { key: "inbox", title: "Inbox", href: "/inbox", icon: Inbox, shortcut: "1" },
  { key: "canvas", title: "Canvas", href: "/canvas", icon: Network, shortcut: "2" },
  { key: "ai", title: "AI", href: "#ai", icon: Brain, shortcut: "3" }, // toggles panel, not nav
  { key: "dashboard", title: "Dashboard", href: "/dashboard", icon: LayoutDashboard, shortcut: "4" },
];
```

- [ ] **Step 2: Create connector registry**

```ts
// web/lib/connector-registry.ts
import {
  BookOpen, FileText, Github, Globe, Highlighter,
  Newspaper, Notebook, Rss, type LucideIcon,
} from "lucide-react";

export type ConnectorDef = {
  key: string;
  label: string;
  icon: LucideIcon;
  contentType: string; // matches content_type field on documents
  statusEndpointName: string; // e.g. "readwise" -> /api/readwise/status
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
```

- [ ] **Step 3: Commit**

```bash
git add web/lib/navigation.ts web/lib/connector-registry.ts
git commit -m "feat(web): replace sidebar nav with 4-pillar navigation and add connector registry"
```

---

## Task 4: New App Shell

**Files:**
- Create: `web/app/(app)/_components/top-bar.tsx`
- Create: `web/app/(app)/_components/ai-panel.tsx`
- Create: `web/app/(app)/_components/tool-panel.tsx`
- Replace: `web/app/(app)/_components/app-shell.tsx`
- Modify: `web/app/(app)/layout.tsx`
- Modify: `web/app/providers.tsx`
- Modify: `web/app/page.tsx`

- [ ] **Step 1: Create TopBar component**

```tsx
// web/app/(app)/_components/top-bar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";
import { AppCommandPaletteTrigger } from "@/components/app-command-palette";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { isClerkEnabled } from "@/lib/auth";
import { pillars } from "@/lib/navigation";
import { useShellStore } from "@/lib/stores/shell-store";

export function TopBar() {
  const pathname = usePathname();
  const toggleAiPanel = useShellStore((s) => s.toggleAiPanel);
  const aiPanelOpen = useShellStore((s) => s.aiPanelOpen);
  const clerkEnabled = isClerkEnabled();

  return (
    <header className="bg-background/90 supports-[backdrop-filter]:bg-background/60 sticky top-0 z-40 border-b backdrop-blur">
      <div className="flex h-12 items-center justify-between px-4">
        <div className="flex items-center gap-1">
          <Link href="/inbox" className="mr-4 flex items-center gap-2 font-semibold tracking-tight">
            <span className="text-primary text-lg">◆</span>
            <span className="hidden sm:inline">Alfred</span>
          </Link>
          <nav className="flex items-center gap-0.5" aria-label="Primary navigation">
            {pillars.map((p) => {
              if (p.key === "ai") {
                return (
                  <Tooltip key={p.key}>
                    <TooltipTrigger asChild>
                      <Button
                        variant={aiPanelOpen ? "secondary" : "ghost"}
                        size="sm"
                        onClick={toggleAiPanel}
                        className="gap-1.5"
                      >
                        <p.icon className="size-4" />
                        <span className="hidden md:inline">{p.title}</span>
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Toggle AI Panel (⌘J)</TooltipContent>
                  </Tooltip>
                );
              }

              const isActive = pathname === p.href || pathname.startsWith(`${p.href}/`);
              return (
                <Tooltip key={p.key}>
                  <TooltipTrigger asChild>
                    <Button variant={isActive ? "secondary" : "ghost"} size="sm" asChild className="gap-1.5">
                      <Link href={p.href}>
                        <p.icon className="size-4" />
                        <span className="hidden md:inline">{p.title}</span>
                      </Link>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{p.title} (⌘{p.shortcut})</TooltipContent>
                </Tooltip>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-1.5">
          <AppCommandPaletteTrigger />
          <ThemeToggle />
          {clerkEnabled ? (
            <>
              <SignedOut>
                <SignInButton mode="modal">
                  <Button size="sm" variant="ghost">Sign in</Button>
                </SignInButton>
              </SignedOut>
              <SignedIn>
                <UserButton />
              </SignedIn>
            </>
          ) : null}
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Create AI Panel component**

```tsx
// web/app/(app)/_components/ai-panel.tsx
"use client";

import { useEffect, useRef, useState } from "react";

import { Send, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAiPanelStore } from "@/lib/stores/ai-panel-store";
import { useShellStore } from "@/lib/stores/shell-store";

export function AiPanel() {
  const { aiPanelOpen, toggleAiPanel } = useShellStore();
  const { messages, isStreaming, sendMessage, clearHistory } = useAiPanelStore();
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!aiPanelOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput("");
    await sendMessage(text);
  };

  return (
    <aside className="border-l bg-background flex h-full w-[380px] shrink-0 flex-col">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <h2 className="text-sm font-semibold">Alfred AI</h2>
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" className="size-7" onClick={clearHistory} title="Clear">
            <span className="text-xs">Clear</span>
          </Button>
          <Button variant="ghost" size="icon" className="size-7" onClick={toggleAiPanel}>
            <X className="size-4" />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-muted-foreground text-sm space-y-2 pt-8 text-center">
            <p>Ask anything about your knowledge...</p>
            <p className="text-xs">Try: &quot;What do I know about distributed systems?&quot;</p>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={i} className={`text-sm ${msg.role === "user" ? "text-right" : ""}`}>
              <div
                className={`inline-block max-w-[90%] rounded-lg px-3 py-2 ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))
        )}
        {isStreaming && (
          <div className="text-muted-foreground text-sm">
            <span className="animate-pulse">Thinking...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="border-t p-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your knowledge..."
            className="bg-muted flex-1 rounded-md px-3 py-2 text-sm outline-none"
            disabled={isStreaming}
          />
          <Button type="submit" size="icon" disabled={isStreaming || !input.trim()}>
            <Send className="size-4" />
          </Button>
        </div>
      </form>
    </aside>
  );
}
```

- [ ] **Step 3: Create ToolPanel container**

```tsx
// web/app/(app)/_components/tool-panel.tsx
"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useShellStore } from "@/lib/stores/shell-store";

export function ToolPanel() {
  const { toolPanel, closeToolPanel } = useShellStore();

  if (!toolPanel) return null;

  const labels: Record<string, string> = {
    notes: "Notes",
    document: "Document",
    connectors: "Connectors",
    quiz: "Review Session",
    writing: "Writing Assistant",
  };

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-[60vw] max-w-3xl flex-col border-l bg-background shadow-xl">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <h2 className="text-sm font-semibold">{labels[toolPanel.type] ?? toolPanel.type}</h2>
        <Button variant="ghost" size="icon" className="size-7" onClick={closeToolPanel}>
          <X className="size-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <p className="text-muted-foreground text-sm">
          {toolPanel.type} panel — content will be migrated here.
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Replace AppShell**

Rewrite `web/app/(app)/_components/app-shell.tsx`:

```tsx
"use client";

import { useEffect } from "react";

import { useShellStore } from "@/lib/stores/shell-store";

import { AiPanel } from "./ai-panel";
import { ToolPanel } from "./tool-panel";
import { TopBar } from "./top-bar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { toggleAiPanel } = useShellStore();

  useEffect(() => {
    const pillarRoutes = ["/inbox", "/canvas", "#ai", "/dashboard"];
    const handler = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) {
        if (e.key === "Escape") {
          useShellStore.getState().closeToolPanel();
        }
        return;
      }
      // Cmd-J: toggle AI panel
      if (e.key === "j") {
        e.preventDefault();
        toggleAiPanel();
      }
      // Cmd-1/2/3/4: pillar navigation
      const num = parseInt(e.key, 10);
      if (num >= 1 && num <= 4) {
        e.preventDefault();
        const route = pillarRoutes[num - 1];
        if (route === "#ai") {
          toggleAiPanel();
        } else {
          window.location.href = route;
        }
      }
      // Cmd-N: new note
      if (e.key === "n") {
        e.preventDefault();
        useShellStore.getState().openToolPanel("notes");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [toggleAiPanel]);

  return (
    <div className="flex h-dvh flex-col">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <main id="main-content" tabIndex={-1} className="flex-1 overflow-y-auto focus:outline-none">
          {children}
        </main>
        <AiPanel />
      </div>
      <ToolPanel />
    </div>
  );
}
```

- [ ] **Step 5: Update layout.tsx to use new shell**

Rewrite `web/app/(app)/layout.tsx`:

```tsx
import { redirect } from "next/navigation";

import { auth } from "@clerk/nextjs/server";

import { AppShell } from "@/app/(app)/_components/app-shell";
import { isClerkEnabled } from "@/lib/auth";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  if (isClerkEnabled()) {
    const { userId } = await auth();
    if (!userId) {
      redirect("/sign-in");
    }
  }

  return <AppShell>{children}</AppShell>;
}
```

- [ ] **Step 6: Update root page.tsx redirect**

Change `web/app/page.tsx` to redirect to `/inbox` instead of `/dashboard`:

```tsx
import { redirect } from "next/navigation";

import { auth } from "@clerk/nextjs/server";

import HeroSection from "@/components/hero-sections-05";
import { isClerkEnabled } from "@/lib/auth";

export default async function Home() {
  if (isClerkEnabled()) {
    try {
      const { userId } = await auth();
      if (userId) {
        redirect("/inbox");
      }
    } catch {
      // Clerk middleware may not have run — fall through to landing.
    }
  }

  return <HeroSection />;
}
```

- [ ] **Step 7: Update providers.tsx**

Remove `AssistantProvider`, `AssistantSheet`, and `TaskCenterSheet` from `web/app/providers.tsx` (AI panel is now in the shell, task center is removed per spec):

```tsx
"use client";

import { useState } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AppCommandPaletteProvider } from "@/components/app-command-palette";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { TaskTrackerProvider } from "@/features/tasks/task-tracker-provider";

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        refetchOnWindowFocus: false,
        staleTime: 30_000,
      },
    },
  });
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => createQueryClient());

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      enableColorScheme
      disableTransitionOnChange
    >
      <QueryClientProvider client={queryClient}>
        <TaskTrackerProvider>
          <AppCommandPaletteProvider>
            <a
              href="#main-content"
              className="focus:bg-background focus:text-foreground focus:ring-ring sr-only fixed top-4 left-4 z-50 rounded-md px-3 py-2 text-sm shadow-sm focus:not-sr-only focus:ring-2 focus:outline-none"
            >
              Skip to content
            </a>
            {children}
            <Toaster />
          </AppCommandPaletteProvider>
        </TaskTrackerProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
```

- [ ] **Step 8: Verify the shell renders**

```bash
cd web && pnpm dev
```

Open `http://localhost:3000/inbox` — you should see the new top bar with 4 pillar icons, an empty main content area, and the AI panel toggle working via Cmd-J.

- [ ] **Step 9: Commit**

```bash
git add web/app/(app)/_components/ web/app/(app)/layout.tsx web/app/page.tsx web/app/providers.tsx
git commit -m "feat(web): new app shell with top bar, AI panel, and tool panel infrastructure"
```

---

## Task 5: Knowledge Inbox

**Files:**
- Create: `web/app/(app)/inbox/page.tsx`
- Create: `web/app/(app)/inbox/_components/inbox-stream.tsx`
- Create: `web/app/(app)/inbox/_components/inbox-filters.tsx`
- Create: `web/app/(app)/inbox/_components/inbox-item.tsx`
- Create: `web/app/(app)/inbox/_components/inbox-detail.tsx`

- [ ] **Step 1: Create inbox page**

```tsx
// web/app/(app)/inbox/page.tsx
import { InboxStream } from "./_components/inbox-stream";

export const metadata = { title: "Inbox — Alfred" };

export default function InboxPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <InboxStream />
    </div>
  );
}
```

- [ ] **Step 2: Create InboxFilters**

```tsx
// web/app/(app)/inbox/_components/inbox-filters.tsx
"use client";

import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { connectors } from "@/lib/connector-registry";

type Props = {
  activeTab: string;
  onTabChange: (tab: string) => void;
  search: string;
  onSearchChange: (val: string) => void;
};

const tabs = [{ key: "all", label: "All" }, ...connectors.map((c) => ({ key: c.key, label: c.label }))];

export function InboxFilters({ activeTab, onTabChange, search, onSearchChange }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex gap-1 overflow-x-auto border-b">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => onTabChange(tab.key)}
            className={`whitespace-nowrap px-3 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "border-primary text-foreground border-b-2"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="relative">
        <Search className="text-muted-foreground absolute left-3 top-1/2 size-4 -translate-y-1/2" />
        <Input
          placeholder="Search your knowledge..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9"
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create InboxItem**

```tsx
// web/app/(app)/inbox/_components/inbox-item.tsx
"use client";

import { formatDistanceToNow } from "date-fns";
import { FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";

type Props = {
  id: string;
  title: string | null;
  summary: string | null;
  sourceUrl: string | null;
  primaryTopic: string | null;
  createdAt: string;
  onClick: () => void;
};

export function InboxItem({ id, title, summary, sourceUrl, primaryTopic, createdAt, onClick }: Props) {
  const timeAgo = formatDistanceToNow(new Date(createdAt), { addSuffix: true });

  return (
    <button
      onClick={onClick}
      className="hover:bg-muted/50 w-full rounded-lg border p-4 text-left transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <FileText className="text-muted-foreground mt-0.5 size-5 shrink-0" />
          <div className="min-w-0">
            <h3 className="truncate font-medium">{title || "Untitled"}</h3>
            {summary && (
              <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">{summary}</p>
            )}
            <div className="mt-2 flex items-center gap-2">
              {primaryTopic && <Badge variant="secondary">{primaryTopic}</Badge>}
              <Badge variant="outline">New</Badge>
            </div>
          </div>
        </div>
        <span className="text-muted-foreground shrink-0 text-xs">{timeAgo}</span>
      </div>
    </button>
  );
}
```

- [ ] **Step 4: Create InboxDetail**

```tsx
// web/app/(app)/inbox/_components/inbox-detail.tsx
"use client";

import { useDocumentDetails } from "@/features/documents/queries";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

type Props = {
  docId: string;
  onClose: () => void;
};

export function InboxDetail({ docId, onClose }: Props) {
  const { data, isLoading } = useDocumentDetails(docId);

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-[50vw] max-w-2xl flex-col border-l bg-background shadow-xl">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <h2 className="truncate text-sm font-semibold">{data?.title ?? "Document"}</h2>
        <Button variant="ghost" size="icon" className="size-7" onClick={onClose}>
          <X className="size-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ) : data ? (
          <article className="prose prose-sm dark:prose-invert max-w-none">
            <h1>{data.title}</h1>
            {data.source_url && (
              <p className="text-muted-foreground text-xs">
                Source: <a href={data.source_url} target="_blank" rel="noopener noreferrer">{data.source_url}</a>
              </p>
            )}
            <div className="whitespace-pre-wrap">{data.cleaned_text}</div>
          </article>
        ) : (
          <p className="text-muted-foreground">Document not found.</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create InboxStream (ties it all together)**

```tsx
// web/app/(app)/inbox/_components/inbox-stream.tsx
"use client";

import { useCallback, useMemo, useState } from "react";

import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useExplorerDocuments } from "@/features/documents/queries";

import { InboxDetail } from "./inbox-detail";
import { InboxFilters } from "./inbox-filters";
import { InboxItem } from "./inbox-item";

export function InboxStream() {
  const [activeTab, setActiveTab] = useState("all");
  const [search, setSearch] = useState("");
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

  const filterTopic = ""; // TODO: wire to topic dropdown
  const { data, isLoading, hasNextPage, fetchNextPage, isFetchingNextPage } = useExplorerDocuments({
    limit: 24,
    filterTopic: filterTopic || undefined,
    search: search || undefined,
  });

  const items = useMemo(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );

  return (
    <div className="space-y-4">
      <InboxFilters
        activeTab={activeTab}
        onTabChange={setActiveTab}
        search={search}
        onSearchChange={setSearch}
      />

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg border bg-muted" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="py-16 text-center">
          <p className="text-muted-foreground">Your knowledge inbox is empty.</p>
          <p className="text-muted-foreground text-sm mt-1">Connect a source or paste a URL to get started.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <InboxItem
              key={item.id}
              id={item.id}
              title={item.title}
              summary={item.summary}
              sourceUrl={item.source_url}
              primaryTopic={item.primary_topic}
              createdAt={item.created_at}
              onClick={() => setSelectedDocId(item.id)}
            />
          ))}
        </div>
      )}

      {hasNextPage && (
        <div className="flex justify-center py-4">
          <Button variant="outline" onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>
            {isFetchingNextPage ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
            Load more
          </Button>
        </div>
      )}

      {selectedDocId && (
        <InboxDetail docId={selectedDocId} onClose={() => setSelectedDocId(null)} />
      )}
    </div>
  );
}
```

- [ ] **Step 6: Verify Inbox renders**

```bash
cd web && pnpm dev
```

Open `http://localhost:3000/inbox` — you should see the filter bar, skeleton loaders, and then either the document stream or the empty state. Click an item to see the detail slide-over.

- [ ] **Step 7: Commit**

```bash
git add web/app/\(app\)/inbox/
git commit -m "feat(web): Knowledge Inbox with stream, filters, item cards, and detail panel"
```

---

## Task 6: Dashboard

**Files:**
- Create: `web/app/(app)/dashboard/_components/knowledge-score.tsx`
- Create: `web/app/(app)/dashboard/_components/retention-card.tsx`
- Create: `web/app/(app)/dashboard/_components/coverage-card.tsx`
- Create: `web/app/(app)/dashboard/_components/connections-card.tsx`
- Create: `web/app/(app)/dashboard/_components/activity-strip.tsx`
- Replace: `web/app/(app)/dashboard/page.tsx`

- [ ] **Step 1: Create KnowledgeScore hero**

```tsx
// web/app/(app)/dashboard/_components/knowledge-score.tsx
"use client";

import { Card, CardContent } from "@/components/ui/card";

type Props = {
  retention: number;
  coverage: number;
  connections: number;
};

export function KnowledgeScore({ retention, coverage, connections }: Props) {
  const score = Math.round(0.4 * retention + 0.3 * coverage + 0.3 * connections);

  return (
    <Card>
      <CardContent className="flex items-center gap-6 p-6">
        <div className="flex size-20 items-center justify-center rounded-full border-4 border-primary">
          <span className="text-3xl font-bold">{score}</span>
        </div>
        <div>
          <h2 className="text-lg font-semibold">Knowledge Score</h2>
          <div className="text-muted-foreground mt-1 flex gap-4 text-sm">
            <span>Retention: {retention}</span>
            <span>Coverage: {coverage}</span>
            <span>Connections: {connections}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Create RetentionCard**

```tsx
// web/app/(app)/dashboard/_components/retention-card.tsx
"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

type RetentionMetric = { retention_rate_30d: number; sample_size: number };

export function RetentionCard() {
  const { data, isLoading } = useQuery({
    queryKey: ["learning", "retention"],
    queryFn: () => apiFetch<RetentionMetric>(apiRoutes.learning.retentionMetrics),
    staleTime: 60_000,
  });

  const dueQuery = useQuery({
    queryKey: ["zettels", "reviews", "due"],
    queryFn: () => apiFetch<unknown[]>(apiRoutes.zettels.reviewsDue),
    staleTime: 60_000,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Retention</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <>
            <div className="text-2xl font-bold">
              {Math.round((data?.retention_rate_30d ?? 0) * 100)}%
              <span className="text-muted-foreground text-sm font-normal ml-2">30-day retention</span>
            </div>
            <div className="text-muted-foreground text-sm">
              {dueQuery.data?.length ?? 0} concepts due for review
            </div>
            <Button size="sm" variant="outline">Start Review Session</Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: Create CoverageCard**

```tsx
// web/app/(app)/dashboard/_components/coverage-card.tsx
"use client";

import { useMemo } from "react";

import { useExplorerDocuments } from "@/features/documents/queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function CoverageCard() {
  // Fallback: aggregate from first batch of explorer docs
  const { data, isLoading } = useExplorerDocuments({ limit: 200 });

  const topicCounts = useMemo(() => {
    const items = data?.pages.flatMap((p) => p.items) ?? [];
    const counts: Record<string, number> = {};
    for (const item of items) {
      const topic = item.primary_topic || "Uncategorized";
      counts[topic] = (counts[topic] ?? 0) + 1;
    }
    return Object.entries(counts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 10);
  }, [data]);

  const uniqueTopics = topicCounts.length;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Coverage</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : topicCounts.length === 0 ? (
          <p className="text-muted-foreground text-sm">Not enough data yet.</p>
        ) : (
          <>
            <div className="text-2xl font-bold">
              {uniqueTopics} <span className="text-muted-foreground text-sm font-normal">topics</span>
            </div>
            <div className="space-y-1">
              {topicCounts.map(([topic, count]) => (
                <div key={topic} className="flex items-center justify-between text-sm">
                  <span className="truncate">{topic}</span>
                  <span className="text-muted-foreground">{count}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Create ConnectionsCard**

```tsx
// web/app/(app)/dashboard/_components/connections-card.tsx
"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

type GraphData = { nodes: { id: number; degree: number }[]; edges: unknown[] };

export function ConnectionsCard() {
  const { data, isLoading } = useQuery({
    queryKey: ["zettels", "graph"],
    queryFn: () => apiFetch<GraphData>(apiRoutes.zettels.graph),
    staleTime: 60_000,
  });

  const nodeCount = data?.nodes.length ?? 0;
  const edgeCount = data?.edges.length ?? 0;
  const density = nodeCount > 0 ? (edgeCount / nodeCount).toFixed(1) : "0";
  const orphans = data?.nodes.filter((n) => n.degree === 0).length ?? 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Connections</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <>
            <div className="flex gap-6 text-sm">
              <div><span className="text-2xl font-bold">{density}</span> edges/node</div>
              <div><span className="text-2xl font-bold">{orphans}</span> orphans</div>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" asChild>
                <a href="/canvas">Open Canvas</a>
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 5: Create ActivityStrip**

```tsx
// web/app/(app)/dashboard/_components/activity-strip.tsx
"use client";

import { useMemo } from "react";

import { subDays, format, startOfDay } from "date-fns";

import { useExplorerDocuments } from "@/features/documents/queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ActivityStrip() {
  const { data } = useExplorerDocuments({ limit: 100 });

  const dayCounts = useMemo(() => {
    const items = data?.pages.flatMap((p) => p.items) ?? [];
    const now = new Date();
    const days = Array.from({ length: 7 }, (_, i) => {
      const date = startOfDay(subDays(now, 6 - i));
      return { date, label: format(date, "EEE"), count: 0 };
    });

    for (const item of items) {
      const itemDate = startOfDay(new Date(item.created_at));
      const match = days.find((d) => d.date.getTime() === itemDate.getTime());
      if (match) match.count += 1;
    }
    return days;
  }, [data]);

  const maxCount = Math.max(1, ...dayCounts.map((d) => d.count));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Activity (7 days)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-2 h-16">
          {dayCounts.map((d) => (
            <div key={d.label} className="flex flex-1 flex-col items-center gap-1">
              <div
                className="w-full rounded-sm bg-primary"
                style={{ height: `${Math.max(4, (d.count / maxCount) * 100)}%` }}
              />
              <span className="text-muted-foreground text-[10px]">{d.label}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 6: Replace dashboard page**

```tsx
// web/app/(app)/dashboard/page.tsx
import { KnowledgeScore } from "./_components/knowledge-score";
import { RetentionCard } from "./_components/retention-card";
import { CoverageCard } from "./_components/coverage-card";
import { ConnectionsCard } from "./_components/connections-card";
import { ActivityStrip } from "./_components/activity-strip";

export const metadata = { title: "Dashboard — Alfred" };

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-6">
      {/* Knowledge Score will be wired to real data via client component wrapper */}
      <KnowledgeScore retention={0} coverage={0} connections={0} />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <RetentionCard />
        <CoverageCard />
        <ConnectionsCard />
      </div>

      <ActivityStrip />
    </div>
  );
}
```

- [ ] **Step 7: Verify Dashboard renders**

```bash
cd web && pnpm dev
```

Open `http://localhost:3000/dashboard` — you should see the Knowledge Score hero, three metric cards, and the activity strip. Cards should load data from the backend and show skeletons while loading.

- [ ] **Step 8: Commit**

```bash
git add web/app/\(app\)/dashboard/
git commit -m "feat(web): Dashboard with Knowledge Score, Retention, Coverage, Connections, and Activity"
```

---

## Task 7: Install @xyflow/react & Canvas Scaffold

**Files:**
- Modify: `web/package.json`
- Create: `web/app/(app)/canvas/page.tsx`
- Create: `web/app/(app)/canvas/[canvasId]/page.tsx`
- Create: `web/app/(app)/canvas/_components/canvas-workspace.tsx`
- Create: `web/app/(app)/canvas/_components/canvas-toolbar.tsx`
- Create: `web/app/(app)/canvas/_components/canvas-node-document.tsx`
- Create: `web/app/(app)/canvas/_components/canvas-node-zettel.tsx`

- [ ] **Step 1: Install @xyflow/react**

```bash
cd web && pnpm add @xyflow/react
```

- [ ] **Step 2: Create custom node components**

```tsx
// web/app/(app)/canvas/_components/canvas-node-document.tsx
"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { FileText } from "lucide-react";

type DocumentNodeData = { label: string; summary?: string };

function DocumentNode({ data }: NodeProps) {
  const d = data as DocumentNodeData;
  return (
    <div className="rounded-lg border bg-background p-3 shadow-sm w-48">
      <Handle type="target" position={Position.Left} className="!bg-primary" />
      <div className="flex items-start gap-2">
        <FileText className="size-4 text-blue-500 shrink-0 mt-0.5" />
        <div className="min-w-0">
          <p className="truncate text-xs font-medium">{d.label}</p>
          {d.summary && <p className="text-muted-foreground mt-1 line-clamp-2 text-[10px]">{d.summary}</p>}
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-primary" />
    </div>
  );
}

export default memo(DocumentNode);
```

```tsx
// web/app/(app)/canvas/_components/canvas-node-zettel.tsx
"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { StickyNote } from "lucide-react";

type ZettelNodeData = { label: string; tags?: string[] };

function ZettelNode({ data }: NodeProps) {
  const d = data as ZettelNodeData;
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-50 dark:bg-amber-950/20 p-3 shadow-sm w-48">
      <Handle type="target" position={Position.Left} className="!bg-amber-500" />
      <div className="flex items-start gap-2">
        <StickyNote className="size-4 text-amber-500 shrink-0 mt-0.5" />
        <p className="truncate text-xs font-medium">{d.label}</p>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-amber-500" />
    </div>
  );
}

export default memo(ZettelNode);
```

- [ ] **Step 3: Create concept node and edge components**

```tsx
// web/app/(app)/canvas/_components/canvas-node-concept.tsx
"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Lightbulb } from "lucide-react";

type ConceptNodeData = { label: string; description?: string };

function ConceptNode({ data }: NodeProps) {
  const d = data as ConceptNodeData;
  return (
    <div className="rounded-lg border border-purple-500/30 bg-purple-50 dark:bg-purple-950/20 p-3 shadow-sm w-48">
      <Handle type="target" position={Position.Left} className="!bg-purple-500" />
      <div className="flex items-start gap-2">
        <Lightbulb className="size-4 text-purple-500 shrink-0 mt-0.5" />
        <div className="min-w-0">
          <p className="truncate text-xs font-medium">{d.label}</p>
          {d.description && <p className="text-muted-foreground mt-1 line-clamp-2 text-[10px]">{d.description}</p>}
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-purple-500" />
    </div>
  );
}

export default memo(ConceptNode);
```

```tsx
// web/app/(app)/canvas/_components/canvas-edge.tsx
"use client";

import { memo } from "react";
import { BaseEdge, getSmoothStepPath, type EdgeProps } from "@xyflow/react";

function CanvasEdge(props: EdgeProps) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data } = props;
  const isAiSuggested = (data as { aiSuggested?: boolean })?.aiSuggested ?? false;

  const [edgePath] = getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });

  return (
    <BaseEdge
      path={edgePath}
      style={{
        stroke: isAiSuggested ? "var(--color-muted-foreground)" : "var(--color-primary)",
        strokeWidth: isAiSuggested ? 1 : 2,
        strokeDasharray: isAiSuggested ? "5 5" : "none",
        opacity: isAiSuggested ? 0.5 : 1,
      }}
    />
  );
}

export default memo(CanvasEdge);
```

```tsx
// web/app/(app)/canvas/_components/canvas-selector.tsx
"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCanvasStore } from "@/lib/stores/canvas-store";

type Whiteboard = { id: number; title: string };

export function CanvasSelector() {
  const { activeCanvasId, setActiveCanvas } = useCanvasStore();

  const { data: boards } = useQuery({
    queryKey: ["whiteboards"],
    queryFn: () => apiFetch<Whiteboard[]>(apiRoutes.whiteboards.list),
    staleTime: 30_000,
  });

  if (!boards || boards.length === 0) return null;

  return (
    <Select value={activeCanvasId ?? undefined} onValueChange={setActiveCanvas}>
      <SelectTrigger className="w-48 h-8 text-xs">
        <SelectValue placeholder="Select canvas" />
      </SelectTrigger>
      <SelectContent>
        {boards.map((b) => (
          <SelectItem key={b.id} value={String(b.id)}>
            {b.title}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
```

- [ ] **Step 4: Create CanvasToolbar**

```tsx
// web/app/(app)/canvas/_components/canvas-toolbar.tsx
"use client";

import { Sparkles, ZoomIn, ZoomOut } from "lucide-react";
import { useReactFlow } from "@xyflow/react";

import { Button } from "@/components/ui/button";
import { useCanvasStore } from "@/lib/stores/canvas-store";

export function CanvasToolbar() {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const { aiSuggestEnabled, toggleAiSuggest } = useCanvasStore();

  return (
    <div className="absolute left-4 top-4 z-10 flex items-center gap-1 rounded-lg border bg-background/90 p-1 shadow-sm backdrop-blur">
      <Button variant="ghost" size="icon" className="size-7" onClick={() => zoomIn()}>
        <ZoomIn className="size-4" />
      </Button>
      <Button variant="ghost" size="icon" className="size-7" onClick={() => zoomOut()}>
        <ZoomOut className="size-4" />
      </Button>
      <Button variant="ghost" size="sm" className="text-xs" onClick={() => fitView()}>
        Fit
      </Button>
      <div className="mx-1 h-4 w-px bg-border" />
      <Button
        variant={aiSuggestEnabled ? "secondary" : "ghost"}
        size="sm"
        className="gap-1 text-xs"
        onClick={toggleAiSuggest}
      >
        <Sparkles className="size-3" />
        AI Suggest
      </Button>
    </div>
  );
}
```

- [ ] **Step 4: Create CanvasWorkspace**

```tsx
// web/app/(app)/canvas/_components/canvas-workspace.tsx
"use client";

import { useCallback, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import CanvasEdge from "./canvas-edge";
import DocumentNode from "./canvas-node-document";
import ConceptNode from "./canvas-node-concept";
import ZettelNode from "./canvas-node-zettel";
import { CanvasToolbar } from "./canvas-toolbar";

const nodeTypes = {
  document: DocumentNode,
  concept: ConceptNode,
  zettel: ZettelNode,
};

const edgeTypes = {
  canvas: CanvasEdge,
};

type Props = {
  initialNodes?: Node[];
  initialEdges?: Edge[];
};

export function CanvasWorkspace({ initialNodes = [], initialEdges = [] }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges],
  );

  return (
    <div className="relative h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        defaultEdgeOptions={{ type: "canvas" }}
        fitView
        className="bg-background"
      >
        <Background gap={20} size={1} />
        <Controls showInteractive={false} className="!bg-background !border !shadow-sm" />
        <MiniMap className="!bg-muted !border" />
        <CanvasToolbar />
      </ReactFlow>
    </div>
  );
}
```

- [ ] **Step 5: Create canvas pages**

```tsx
// web/app/(app)/canvas/page.tsx
import { CanvasWorkspace } from "./_components/canvas-workspace";

export const metadata = { title: "Canvas — Alfred" };

export default function CanvasPage() {
  // Default canvas — loads empty for now. Will wire to whiteboard API.
  return (
    <div className="h-[calc(100dvh-3rem)]">
      <CanvasWorkspace />
    </div>
  );
}
```

```tsx
// web/app/(app)/canvas/[canvasId]/page.tsx
import { CanvasWorkspace } from "../_components/canvas-workspace";

export const metadata = { title: "Canvas — Alfred" };

export default function CanvasDetailPage({ params }: { params: Promise<{ canvasId: string }> }) {
  // Will load canvas state from whiteboard API by canvasId
  return (
    <div className="h-[calc(100dvh-3rem)]">
      <CanvasWorkspace />
    </div>
  );
}
```

- [ ] **Step 6: Verify Canvas renders**

```bash
cd web && pnpm dev
```

Open `http://localhost:3000/canvas` — you should see an empty @xyflow/react canvas with background grid, minimap, controls, and the AI Suggest toolbar. Verify zoom and fit-view work.

- [ ] **Step 7: Commit**

```bash
git add web/package.json web/pnpm-lock.yaml web/app/\(app\)/canvas/
git commit -m "feat(web): Knowledge Canvas with @xyflow/react, custom nodes, and toolbar"
```

---

## Task 8: Update Command Palette

**Files:**
- Modify: `web/components/app-command-palette.tsx`

- [ ] **Step 1: Read the current command palette**

Read `web/components/app-command-palette.tsx` to understand its structure before modifying.

- [ ] **Step 2: Update nav targets and add tool panel triggers**

Update the command palette to:
1. Replace sidebar nav items with the 4 pillars (Inbox, Canvas, Dashboard).
2. Add "AI" command that toggles the AI panel via `useShellStore`.
3. Add tool commands: "New Note", "Connectors", "System Design".
4. Keep the search functionality.

The exact implementation depends on the current structure — read the file first, then modify in place. Key changes:
- Import `pillars` from `@/lib/navigation` instead of `appNavItems`
- Import `useShellStore` for AI panel toggle and tool panel triggers
- Add command groups: "Navigation" (pillars), "Tools" (notes, connectors, system design), "AI Actions" (summarize, research)

- [ ] **Step 3: Commit**

```bash
git add web/components/app-command-palette.tsx
git commit -m "feat(web): update command palette for 4-pillar navigation and tool panel triggers"
```

---

## Task 9: Clean Up Old Routes

**Files:**
- Remove or archive old page routes that are superseded

- [ ] **Step 1: Remove deprecated pages**

Delete (or move to a `_deprecated/` folder if you want to keep them for reference):
- `web/app/(app)/library/` — replaced by Inbox
- `web/app/(app)/rag/` — replaced by AI panel
- `web/app/(app)/tasks/` — replaced by toasts
- `web/app/(app)/calendar/` — removed (job-search era)

Keep:
- `web/app/(app)/documents/` — keep for now as the detail routes may be referenced. Can be removed once Inbox detail panel is fully wired.
- `web/app/(app)/notes/` — keep, will be migrated to tool panel later
- `web/app/(app)/notion/` — keep, will be migrated to connectors panel later
- `web/app/(app)/research/` — keep, will be migrated to AI panel later
- `web/app/(app)/system-design/` — keep as-is (not in the `(app)` group, it's in `(canvas)`)

```bash
rm -rf web/app/\(app\)/library web/app/\(app\)/rag web/app/\(app\)/tasks web/app/\(app\)/calendar
```

- [ ] **Step 2: Remove old sidebar component**

The `AppSidebar` is no longer used. Remove:
- `web/components/app-sidebar.tsx`
- `web/components/app-navigation-menu.tsx`

```bash
rm web/components/app-sidebar.tsx web/components/app-navigation-menu.tsx
```

- [ ] **Step 3: Verify no build errors**

```bash
cd web && pnpm build
```

Fix any import errors from removed files.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore(web): remove deprecated pages (library, rag, tasks, calendar) and old sidebar"
```

---

## Task 10: End-to-End Smoke Test

- [ ] **Step 1: Start backend**

```bash
DATABASE_URL="postgresql+psycopg://dev:devpass@localhost:5432/alfred" uv run uvicorn alfred.main:app --port 8000
```

- [ ] **Step 2: Start frontend**

```bash
cd web && pnpm dev
```

- [ ] **Step 3: Verify all pillar pages**

1. `http://localhost:3000/` — should redirect to `/inbox`
2. `/inbox` — should show filter tabs, search bar, and document stream (with the KM Test doc from earlier)
3. Click the KM Test doc — detail panel should open with full content
4. `/canvas` — should show empty @xyflow canvas with toolbar
5. `/dashboard` — should show Knowledge Score (0), Retention, Coverage, Connections cards
6. Cmd-J — AI panel should toggle open/closed
7. Cmd-K — command palette should show pillar navigation and tool commands
8. `/system-design` — should still work (full-screen Excalidraw, kept as-is)

- [ ] **Step 4: Commit final state**

```bash
git add -A
git commit -m "feat(web): Alfred Knowledge Factory frontend revamp complete — Inbox, Canvas, AI, Dashboard"
```
