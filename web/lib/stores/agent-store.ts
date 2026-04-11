import { create } from "zustand";
import { useShallow } from "zustand/react/shallow";

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
  call_id?: string;
  tool: string;
  args: Record<string, unknown>;
  result?: Record<string, unknown>;
  status: "pending" | "done" | "error";
};

export type PlanTask = {
  id: string;
  agent: "knowledge" | "research" | "connection";
  objective: string;
  status: "queued" | "running" | "done" | "error";
};

export type PendingApproval = {
  id: string;
  action: string;
  reason: string;
  preview: Record<string, unknown>;
};

export type AgentMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  reasoning?: string;
  artifacts: ArtifactCard[];
  relatedCards: RelatedCard[];
  gaps: GapChip[];
  toolCalls: ToolCall[];
  plan: PlanTask[];
  pendingApprovals: PendingApproval[];
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
  set((s) => _updateLastAssistant(s, (m) => ({ ...m, content: m.content + buffered })));
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
  messagesById: Record<string, AgentMessage>;
  messageOrder: string[];
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

// --- Selector: ordered messages from normalized state ---

export function selectOrderedMessages(state: Pick<AgentState, "messagesById" | "messageOrder">): AgentMessage[] {
  return state.messageOrder.map((id) => state.messagesById[id]).filter(Boolean);
}

// --- Derived store: tool calls (separate to avoid re-renders) ---

export function useToolCallStore<T>(selector: (s: { activeToolCalls: ToolCall[] }) => T): T {
  return useAgentStore(useShallow((s) => selector({ activeToolCalls: s.activeToolCalls })));
}

// --- Helper: update last assistant message in normalized state ---

function _updateLastAssistant(
  state: Pick<AgentState, "messagesById" | "messageOrder">,
  updater: (msg: AgentMessage) => AgentMessage,
): Pick<AgentState, "messagesById"> {
  const { messageOrder, messagesById } = state;
  for (let i = messageOrder.length - 1; i >= 0; i--) {
    const id = messageOrder[i];
    const msg = messagesById[id];
    if (msg?.role === "assistant") {
      return { messagesById: { ...messagesById, [id]: updater(msg) } };
    }
  }
  return { messagesById };
}

export const useAgentStore = create<AgentState>((set, get) => ({
  messagesById: {},
  messageOrder: [],
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
      plan: [],
      pendingApprovals: [],
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
      plan: [],
      pendingApprovals: [],
      lens: state.activeLens ?? undefined,
      model: state.activeModel,
      timestamp: Date.now(),
    };

    const abortController = new AbortController();

    set((s) => ({
      messagesById: {
        ...s.messagesById,
        [userMsg.id]: userMsg,
        [assistantMsg.id]: assistantMsg,
      },
      messageOrder: [...s.messageOrder, userMsg.id, assistantMsg.id],
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
            : selectOrderedMessages(state).slice(-20).map((m) => ({
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
        set((s) => _updateLastAssistant(s, (m) =>
          !m.content ? { ...m, content: "Sorry, something went wrong. Please try again." } : m,
        ));
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
      messagesById: {},
      messageOrder: [],
    }));
    return thread;
  },

  loadThread: async (threadId: number) => {
    const data = await apiFetch<{ thread: AgentThread; messages: AgentMessage[] }>(
      apiRoutes.agent.threadById(threadId)
    );
    const normalized = data.messages.reduce(
      (acc, m) => {
        const id = `db-${m.id}`;
        const msg: AgentMessage = {
          ...m,
          id,
          reasoning:
            (m as { reasoning?: string }).reasoning ||
            (m as { reasoning_traces?: string }).reasoning_traces,
          artifacts: m.artifacts || [],
          relatedCards:
            m.relatedCards ||
            (m as { related_cards?: RelatedCard[] }).related_cards ||
            [],
          gaps: m.gaps || [],
          toolCalls:
            m.toolCalls ||
            (m as { tool_calls?: ToolCall[] }).tool_calls ||
            [],
          plan: m.plan || [],
          pendingApprovals: m.pendingApprovals || [],
          timestamp: new Date(
            (m as { createdAt?: string; created_at?: string }).createdAt ||
              (m as { created_at?: string }).created_at ||
              Date.now(),
          ).getTime(),
        };
        acc.messagesById[id] = msg;
        acc.messageOrder.push(id);
        return acc;
      },
      { messagesById: {} as Record<string, AgentMessage>, messageOrder: [] as string[] },
    );
    set({
      activeThreadId: threadId,
      messagesById: normalized.messagesById,
      messageOrder: normalized.messageOrder,
    });
  },

  deleteThread: async (threadId: number) => {
    await apiFetch(apiRoutes.agent.threadById(threadId), { method: "DELETE", headers: { "Content-Type": "application/json" } });
    set((s) => ({
      threads: s.threads.filter((t) => t.id !== threadId),
      activeThreadId: s.activeThreadId === threadId ? null : s.activeThreadId,
      messagesById: s.activeThreadId === threadId ? {} : s.messagesById,
      messageOrder: s.activeThreadId === threadId ? [] : s.messageOrder,
    }));
  },

  clearMessages: () => set({ messagesById: {}, messageOrder: [], activeThreadId: null, noteContext: null }),

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
      messagesById: {},
      messageOrder: [],
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
    case "reasoning": {
      // Collapsible reasoning trace for o3/o4 models
      set((s) =>
        _updateLastAssistant(s, (m) => ({
          ...m,
          reasoning: ((m as Record<string, unknown>).reasoning as string || "") + (data.content as string),
        })),
      );
      break;
    }

    case "token": {
      const content = data.content as string;
      _tokenBuffer += content;
      if (!_tokenFlushTimer) {
        _tokenFlushTimer = setTimeout(() => _flushTokenBuffer(set), 100);
      }
      break;
    }

    case "tool_start": {
      const toolCall: ToolCall = {
        call_id: data.call_id as string | undefined,
        tool: data.tool as string,
        args: data.args as Record<string, unknown>,
        status: "pending",
      };
      set((s) => ({ activeToolCalls: [...s.activeToolCalls, toolCall] }));
      break;
    }

    case "plan": {
      const tasks = ((data.tasks as PlanTask[]) || []).map((task) => ({
        ...task,
        status: task.status || "queued",
      }));
      set((s) => _updateLastAssistant(s, (m) => ({ ...m, plan: tasks })));
      break;
    }

    case "task_start": {
      const taskId = data.task_id as string;
      const agent = data.agent as PlanTask["agent"];
      const objective = data.objective as string;
      set((s) =>
        _updateLastAssistant(s, (m) => {
          const existing = m.plan.find((task) => task.id === taskId);
          const plan = existing
            ? m.plan.map((task) =>
                task.id === taskId ? { ...task, status: "running" as const } : task,
              )
            : [
                ...m.plan,
                { id: taskId, agent, objective, status: "running" as const },
              ];
          return { ...m, plan };
        }),
      );
      break;
    }

    case "task_done": {
      const taskId = data.task_id as string;
      set((s) =>
        _updateLastAssistant(s, (m) => ({
          ...m,
          plan: m.plan.map((task) =>
            task.id === taskId ? { ...task, status: "done" as const } : task,
          ),
        })),
      );
      break;
    }

    case "task_error": {
      const taskId = data.task_id as string;
      set((s) =>
        _updateLastAssistant(s, (m) => ({
          ...m,
          plan: m.plan.map((task) =>
            task.id === taskId ? { ...task, status: "error" as const } : task,
          ),
        })),
      );
      break;
    }

    case "tool_result": {
      const callId = data.call_id as string | undefined;
      set((s) => {
        const tools = s.activeToolCalls.map((tc) =>
          (callId && tc.call_id === callId) || (!callId && tc.status === "pending")
            ? { ...tc, result: data.result as Record<string, unknown>, status: "done" as const }
            : tc,
        );
        return {
          activeToolCalls: tools,
          ..._updateLastAssistant(s, (m) => ({ ...m, toolCalls: [...tools] })),
        };
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
        const lastMsgId = s.messageOrder[s.messageOrder.length - 1];
        const lastMsg = lastMsgId ? s.messagesById[lastMsgId] : undefined;
        const updatedById = lastMsg && lastMsg.role === "assistant"
          ? { ...s.messagesById, [lastMsgId]: { ...lastMsg, toolCalls: [...tools] } }
          : s.messagesById;
        return { activeToolCalls: tools, messagesById: updatedById };
      });
      break;
    }

    case "artifact": {
      const artifact: ArtifactCard = {
        type: (data.type as string) as "zettel" | "document",
        action: (data.action as string) as "created" | "found" | "updated",
        ...(data.zettel as Record<string, unknown>),
      } as ArtifactCard;

      set((s) => _updateLastAssistant(s, (m) => ({ ...m, artifacts: [...m.artifacts, artifact] })));
      break;
    }

    case "related": {
      const cards = (data.cards as RelatedCard[]) || [];
      set((s) => _updateLastAssistant(s, (m) => ({ ...m, relatedCards: cards })));
      break;
    }

    case "gaps": {
      const gaps = (data.gaps as GapChip[]) || [];
      set((s) => _updateLastAssistant(s, (m) => ({ ...m, gaps })));
      break;
    }

    case "approval_required": {
      const actions = ((data.actions as Record<string, unknown>[]) || []).map(
        (action) => ({
          id: String(action.id || ""),
          action: String(action.action || ""),
          reason: String(action.reason || ""),
          preview: (action.payload as Record<string, unknown>) || {},
        }),
      );
      set((s) =>
        _updateLastAssistant(s, (m) => ({ ...m, pendingApprovals: actions })),
      );
      break;
    }

    case "error": {
      set((s) => ({
        ..._updateLastAssistant(s, (m) => ({ ...m, content: (data.message as string) || "Something went wrong." })),
        isStreaming: false,
      }));
      break;
    }

    case "thread_created": {
      const threadId = data.thread_id as number;
      if (threadId) {
        set(() => ({ activeThreadId: threadId }));
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
