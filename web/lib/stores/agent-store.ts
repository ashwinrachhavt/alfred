import { create } from "zustand";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

// --- Types ---

export type ArtifactCard = {
  type: "zettel" | "document";
  action: "created" | "found" | "updated";
  id: number;
  title: string;
  summary: string;
  topic?: string;
  tags: string[];
};

export type RelatedCard = {
  zettelId: number;
  title: string;
  domain: string;
  reason: string;
  score: number;
};

export type GapChip = {
  concept: string;
  description: string;
  confidence: number;
};

export type ToolCall = {
  tool: string;
  args: Record<string, unknown>;
  result?: Record<string, unknown>;
  status: "pending" | "done" | "error";
};

export type AgentMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  artifacts: ArtifactCard[];
  relatedCards: RelatedCard[];
  gaps: GapChip[];
  toolCalls: ToolCall[];
  lens?: string;
  model?: string;
  timestamp: number;
};

export type AgentThread = {
  id: number;
  title: string;
  status: string;
  pinned: boolean;
  activeLens: string | null;
  modelId: string | null;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
};

// --- Philosophical Lenses ---

export const PHILOSOPHICAL_LENSES = [
  { id: "socratic", label: "Socratic" },
  { id: "stoic", label: "Stoic" },
  { id: "existentialist", label: "Existentialist" },
  { id: "utilitarian", label: "Utilitarian" },
  { id: "kantian", label: "Kantian" },
  { id: "virtue_ethics", label: "Virtue Ethics" },
  { id: "eastern", label: "Eastern" },
] as const;

// --- Store ---

type AgentState = {
  messages: AgentMessage[];
  threads: AgentThread[];
  activeThreadId: number | null;
  isStreaming: boolean;
  activeLens: string | null;
  activeModel: string;
  activeToolCalls: ToolCall[];
  abortController: AbortController | null;

  // Actions
  sendMessage: (text: string) => Promise<void>;
  cancelStream: () => void;
  setLens: (lens: string | null) => void;
  setModel: (model: string) => void;
  loadThreads: () => Promise<void>;
  createThread: (title?: string) => Promise<AgentThread>;
  loadThread: (threadId: number) => Promise<void>;
  deleteThread: (threadId: number) => Promise<void>;
  clearMessages: () => void;
};

export const useAgentStore = create<AgentState>((set, get) => ({
  messages: [],
  threads: [],
  activeThreadId: null,
  isStreaming: false,
  activeLens: null,
  activeModel: "gpt-5.4",
  activeToolCalls: [],
  abortController: null,

  sendMessage: async (text: string) => {
    const state = get();

    // Cancel existing stream if active (cancel + send behavior)
    if (state.isStreaming && state.abortController) {
      state.abortController.abort();
    }

    const userMsg: AgentMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      artifacts: [],
      relatedCards: [],
      gaps: [],
      toolCalls: [],
      lens: state.activeLens ?? undefined,
      model: state.activeModel,
      timestamp: Date.now(),
    };

    const assistantMsg: AgentMessage = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content: "",
      artifacts: [],
      relatedCards: [],
      gaps: [],
      toolCalls: [],
      lens: state.activeLens ?? undefined,
      model: state.activeModel,
      timestamp: Date.now(),
    };

    const abortController = new AbortController();

    set((s) => ({
      messages: [...s.messages, userMsg, assistantMsg],
      isStreaming: true,
      activeToolCalls: [],
      abortController,
    }));

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const response = await fetch(`${baseUrl}${apiRoutes.agent.stream}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          thread_id: state.activeThreadId,
          lens: state.activeLens,
          model: state.activeModel,
          history: state.messages.slice(-20).map((m) => ({
            role: m.role,
            content: m.content,
          })),
        }),
        signal: abortController.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`Stream failed: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventType = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ") && eventType) {
            try {
              const data = JSON.parse(line.slice(6));
              _handleSSEEvent(eventType, data, set, get);
            } catch {
              // Skip malformed JSON
            }
            eventType = "";
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // User cancelled — expected
      } else {
        set((s) => {
          const msgs = [...s.messages];
          const last = msgs[msgs.length - 1];
          if (last?.role === "assistant" && !last.content) {
            last.content = "Sorry, something went wrong. Please try again.";
          }
          return { messages: msgs };
        });
      }
    } finally {
      set({ isStreaming: false, abortController: null });
    }
  },

  cancelStream: () => {
    const { abortController } = get();
    if (abortController) {
      abortController.abort();
      set({ isStreaming: false, abortController: null });
    }
  },

  setLens: (lens) => set({ activeLens: lens }),
  setModel: (model) => set({ activeModel: model }),

  loadThreads: async () => {
    try {
      const threads = await apiFetch<AgentThread[]>(apiRoutes.agent.threads);
      set({ threads });
    } catch {
      // Silently fail — threads list is non-critical
    }
  },

  createThread: async (title?: string) => {
    const thread = await apiFetch<AgentThread>(apiRoutes.agent.threads, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    set((s) => ({
      threads: [thread, ...s.threads],
      activeThreadId: thread.id,
      messages: [],
    }));
    return thread;
  },

  loadThread: async (threadId: number) => {
    const data = await apiFetch<{ thread: AgentThread; messages: AgentMessage[] }>(
      apiRoutes.agent.threadById(threadId)
    );
    set({
      activeThreadId: threadId,
      messages: data.messages.map((m) => ({
        ...m,
        id: `db-${m.id}`,
        artifacts: m.artifacts || [],
        relatedCards: m.relatedCards || [],
        gaps: m.gaps || [],
        toolCalls: m.toolCalls || [],
        timestamp: new Date((m as any).createdAt ?? Date.now()).getTime(),
      })),
    });
  },

  deleteThread: async (threadId: number) => {
    await apiFetch(apiRoutes.agent.threadById(threadId), { method: "DELETE", headers: { "Content-Type": "application/json" } });
    set((s) => ({
      threads: s.threads.filter((t) => t.id !== threadId),
      activeThreadId: s.activeThreadId === threadId ? null : s.activeThreadId,
      messages: s.activeThreadId === threadId ? [] : s.messages,
    }));
  },

  clearMessages: () => set({ messages: [], activeThreadId: null }),
}));

// --- SSE event handler ---

function _handleSSEEvent(
  event: string,
  data: Record<string, unknown>,
  set: (fn: (s: AgentState) => Partial<AgentState>) => void,
  _get: () => AgentState,
) {
  switch (event) {
    case "token": {
      const content = data.content as string;
      set((s) => {
        const msgs = [...s.messages];
        const last = msgs[msgs.length - 1];
        if (last?.role === "assistant") {
          last.content += content;
        }
        return { messages: msgs };
      });
      break;
    }

    case "tool_start": {
      const toolCall: ToolCall = {
        tool: data.tool as string,
        args: data.args as Record<string, unknown>,
        status: "pending",
      };
      set((s) => ({ activeToolCalls: [...s.activeToolCalls, toolCall] }));
      break;
    }

    case "tool_result": {
      set((s) => {
        const tools = [...s.activeToolCalls];
        const last = tools[tools.length - 1];
        if (last) {
          last.result = data.result as Record<string, unknown>;
          last.status = "done";
        }
        // Also add tool calls to the assistant message
        const msgs = [...s.messages];
        const lastMsg = msgs[msgs.length - 1];
        if (lastMsg?.role === "assistant") {
          lastMsg.toolCalls = [...tools];
        }
        return { activeToolCalls: tools, messages: msgs };
      });
      break;
    }

    case "artifact": {
      const artifact: ArtifactCard = {
        type: (data.type as string) as "zettel" | "document",
        action: (data.action as string) as "created" | "found" | "updated",
        ...(data.zettel as Record<string, unknown>),
      } as ArtifactCard;

      set((s) => {
        const msgs = [...s.messages];
        const last = msgs[msgs.length - 1];
        if (last?.role === "assistant") {
          last.artifacts = [...last.artifacts, artifact];
        }
        return { messages: msgs };
      });
      break;
    }

    case "related": {
      const cards = (data.cards as RelatedCard[]) || [];
      set((s) => {
        const msgs = [...s.messages];
        const last = msgs[msgs.length - 1];
        if (last?.role === "assistant") {
          last.relatedCards = cards;
        }
        return { messages: msgs };
      });
      break;
    }

    case "error": {
      set((s) => {
        const msgs = [...s.messages];
        const last = msgs[msgs.length - 1];
        if (last?.role === "assistant") {
          last.content = (data.message as string) || "Something went wrong.";
        }
        return { messages: msgs, isStreaming: false };
      });
      break;
    }

    case "done":
      // Stream complete
      break;
  }
}
