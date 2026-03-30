import { create } from "zustand";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { streamSSE } from "@/lib/api/sse";

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

export type NoteContext = {
  noteId: string;
  title: string;
  contentPreview: string;
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

// --- Token buffer (module-level for 50ms batching) ---

let _tokenBuffer = "";
let _tokenFlushTimer: ReturnType<typeof setTimeout> | null = null;

function _flushTokenBuffer(
  set: (fn: (s: AgentState) => Partial<AgentState>) => void,
) {
  if (!_tokenBuffer) return;
  const buffered = _tokenBuffer;
  _tokenBuffer = "";
  _tokenFlushTimer = null;
  set((s) => {
    const msgs = s.messages.map((m, i) =>
      i === s.messages.length - 1 && m.role === "assistant"
        ? { ...m, content: m.content + buffered }
        : m,
    );
    return { messages: msgs };
  });
}

function _clearTokenBuffer() {
  _tokenBuffer = "";
  if (_tokenFlushTimer) {
    clearTimeout(_tokenFlushTimer);
    _tokenFlushTimer = null;
  }
}

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
  noteContext: NoteContext | null;

  // Actions
  sendMessage: (text: string, opts?: { intent?: string; intentArgs?: Record<string, unknown> }) => Promise<void>;
  cancelStream: () => void;
  setLens: (lens: string | null) => void;
  setModel: (model: string) => void;
  loadThreads: () => Promise<void>;
  createThread: (title?: string) => Promise<AgentThread>;
  loadThread: (threadId: number) => Promise<void>;
  deleteThread: (threadId: number) => Promise<void>;
  clearMessages: () => void;
  setNoteContext: (ctx: NoteContext | null) => void;
  loadThreadByNoteId: (noteId: string) => Promise<void>;
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
  noteContext: null,

  sendMessage: async (text: string, opts?: { intent?: string; intentArgs?: Record<string, unknown> }) => {
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
      // Compose abort signals: user cancel + 60s timeout
      const timeoutController = new AbortController();
      const timeoutId = setTimeout(() => timeoutController.abort(), 60000);

      // Compose signals — use AbortSignal.any if available, otherwise manual fallback
      let composedSignal: AbortSignal;
      if (typeof AbortSignal.any === "function") {
        composedSignal = AbortSignal.any([abortController.signal, timeoutController.signal]);
      } else {
        // Fallback: forward either abort to a shared controller
        const shared = new AbortController();
        const forwardAbort = () => shared.abort();
        abortController.signal.addEventListener("abort", forwardAbort, { once: true });
        timeoutController.signal.addEventListener("abort", forwardAbort, { once: true });
        composedSignal = shared.signal;
      }

      await streamSSE(
        apiRoutes.agent.stream,
        {
          message: text,
          thread_id: state.activeThreadId,  // null is fine — backend auto-creates
          note_context: state.noteContext
            ? {
                note_id: state.noteContext.noteId,
                title: state.noteContext.title,
                content_preview: state.noteContext.contentPreview,
              }
            : undefined,
          lens: state.activeLens,
          model: state.activeModel,
          // Only send history if no thread (backend loads from DB when thread exists)
          history: state.activeThreadId
            ? undefined
            : state.messages.slice(-20).map((m) => ({
                role: m.role,
                content: m.content,
              })),
          intent: opts?.intent,
          intent_args: opts?.intentArgs,
        },
        (event, data) => _handleSSEEvent(event, data, set, get),
        composedSignal,
      );

      clearTimeout(timeoutId);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // User cancelled — expected
      } else {
        // Flush any buffered tokens before setting error
        _flushTokenBuffer(set);
        set((s) => {
          const msgs = [...s.messages];
          const last = msgs[msgs.length - 1];
          if (last?.role === "assistant" && !last.content) {
            msgs[msgs.length - 1] = { ...last, content: "Sorry, something went wrong. Please try again." };
          }
          return { messages: msgs };
        });
      }
    } finally {
      // Flush any remaining buffered tokens
      if (_tokenFlushTimer) {
        clearTimeout(_tokenFlushTimer);
        _tokenFlushTimer = null;
      }
      _flushTokenBuffer(set);
      set({ isStreaming: false, abortController: null });
    }
  },

  cancelStream: () => {
    const { abortController } = get();
    if (abortController) {
      abortController.abort();
      _clearTokenBuffer();
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

  clearMessages: () => set({ messages: [], activeThreadId: null, noteContext: null }),

  setNoteContext: (ctx: NoteContext | null) => {
    const state = get();
    // Abort any active stream
    if (state.isStreaming && state.abortController) {
      state.abortController.abort();
      _clearTokenBuffer();
    }
    // Clear current state and set new note context
    set({
      noteContext: ctx,
      messages: [],
      activeThreadId: null,
      isStreaming: false,
      abortController: null,
      activeToolCalls: [],
    });
    // Load thread for new note if context provided
    if (ctx) {
      get().loadThreadByNoteId(ctx.noteId);
    }
  },

  loadThreadByNoteId: async (noteId: string) => {
    try {
      const threads = await apiFetch<AgentThread[]>(`${apiRoutes.agent.threads}?note_id=${noteId}`);
      if (threads.length > 0) {
        await get().loadThread(threads[0].id);
      }
    } catch {
      // Silent — no thread exists yet
    }
  },
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
      _tokenBuffer += content;
      if (!_tokenFlushTimer) {
        _tokenFlushTimer = setTimeout(() => _flushTokenBuffer(set), 50);
      }
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
        const tools = s.activeToolCalls.map((tc, i) =>
          i === s.activeToolCalls.length - 1
            ? { ...tc, result: data.result as Record<string, unknown>, status: "done" as const }
            : tc,
        );
        const msgs = s.messages.map((m, i) =>
          i === s.messages.length - 1 && m.role === "assistant"
            ? { ...m, toolCalls: [...tools] }
            : m,
        );
        return { activeToolCalls: tools, messages: msgs };
      });
      break;
    }

    case "tool_end": {
      set((s) => {
        const tools = s.activeToolCalls.map((tc, i) =>
          i === s.activeToolCalls.length - 1
            ? { ...tc, result: data as Record<string, unknown>, status: "done" as const }
            : tc,
        );
        const msgs = s.messages.map((m, i) =>
          i === s.messages.length - 1 && m.role === "assistant"
            ? { ...m, toolCalls: [...tools] }
            : m,
        );
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
        const msgs = s.messages.map((m, i) =>
          i === s.messages.length - 1 && m.role === "assistant"
            ? { ...m, artifacts: [...m.artifacts, artifact] }
            : m,
        );
        return { messages: msgs };
      });
      break;
    }

    case "related": {
      const cards = (data.cards as RelatedCard[]) || [];
      set((s) => {
        const msgs = s.messages.map((m, i) =>
          i === s.messages.length - 1 && m.role === "assistant"
            ? { ...m, relatedCards: cards }
            : m,
        );
        return { messages: msgs };
      });
      break;
    }

    case "gaps": {
      const gaps = (data.gaps as GapChip[]) || [];
      set((s) => {
        const msgs = s.messages.map((m, i) =>
          i === s.messages.length - 1 && m.role === "assistant"
            ? { ...m, gaps }
            : m,
        );
        return { messages: msgs };
      });
      break;
    }

    case "error": {
      set((s) => {
        const msgs = s.messages.map((m, i) =>
          i === s.messages.length - 1 && m.role === "assistant"
            ? { ...m, content: (data.message as string) || "Something went wrong." }
            : m,
        );
        return { messages: msgs, isStreaming: false };
      });
      break;
    }

    case "thread_created": {
      const threadId = data.thread_id as number;
      if (threadId) {
        set({ activeThreadId: threadId });
      }
      break;
    }

    case "done":
      // Flush any remaining buffered tokens
      if (_tokenFlushTimer) {
        clearTimeout(_tokenFlushTimer);
        _tokenFlushTimer = null;
      }
      _flushTokenBuffer(set);
      break;
  }
}
