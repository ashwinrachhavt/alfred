import { create } from "zustand";
import { useShallow } from "zustand/react/shallow";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { streamSSE } from "@/lib/api/sse";
import { DEFAULT_AI_MODEL } from "@/lib/constants/ai";
import { createAguiEventProjector } from "@/lib/streaming/agui-runtime";
import { notifyStreamCacheEvent } from "@/lib/streaming/reactive-cache";

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

// --- Message parts (AI Elements migration — Task 2) ---
// These types drive the new AI Elements primitives. The store dual-writes
// them alongside the legacy `content`/`reasoning`/`toolCalls`/`plan` fields
// until Task 6 swaps the MessageBubble consumer.

export type TextPart = {
  type: "text";
  text: string;
  state?: "streaming" | "done";
};

export type ReasoningPart = {
  type: "reasoning";
  text: string;
  state: "streaming" | "done";
  startedAt: number;
  finishedAt?: number;
};

export type ToolState =
  | "input-streaming"
  | "input-available"
  | "output-available"
  | "output-error";

// One member per tool known to the backend. Keep `type` as a string template
// literal so <Tool type={part.type}> can consume it directly.
export type SearchKbPart = {
  type: "tool-search_kb";
  toolCallId: string;
  state: ToolState;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  errorText?: string;
};
export type CreateZettelPart = {
  type: "tool-create_zettel";
  toolCallId: string;
  state: ToolState;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  errorText?: string;
};
export type GetZettelPart = {
  type: "tool-get_zettel";
  toolCallId: string;
  state: ToolState;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  errorText?: string;
};
export type UpdateZettelPart = {
  type: "tool-update_zettel";
  toolCallId: string;
  state: ToolState;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  errorText?: string;
};
export type DeepResearchPart = {
  type: "tool-deep_research";
  toolCallId: string;
  state: ToolState;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  errorText?: string;
};
export type FirecrawlScrapePart = {
  type: "tool-firecrawl_scrape";
  toolCallId: string;
  state: ToolState;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  errorText?: string;
};

// Fallback for tools we don't have a specific type for (future-proofing).
export type UnknownToolPart = {
  type: `tool-${string}`;
  toolCallId: string;
  state: ToolState;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  errorText?: string;
};

export type StepPart = {
  type: "step";
  label: string;
  description?: string;
  state: "pending" | "active" | "complete" | "error";
  taskId?: string;
};

export type SourcePart = {
  type: "source-url";
  url: string;
  title?: string;
};

export type ImagePart = {
  type: "image";
  url: string;
  mimeType?: string;
  name?: string;
  size?: number;
  state?: "done";
};

export type MessagePart =
  | TextPart
  | ReasoningPart
  | SearchKbPart
  | CreateZettelPart
  | GetZettelPart
  | UpdateZettelPart
  | DeepResearchPart
  | FirecrawlScrapePart
  | UnknownToolPart
  | StepPart
  | SourcePart
  | ImagePart;

export type ChatImageAttachment = {
  id: string;
  kind: "image";
  name: string;
  mimeType: string;
  size: number;
  dataUrl: string;
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
  /**
   * AI Elements parts — dual-written alongside the legacy fields above.
   * Consumers have not yet migrated; this exists to be populated now so
   * Task 6 (MessageBubble swap) and Task 4 (persistence) can switch over
   * without a coordinated flip-day.
   */
  parts: MessagePart[];
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
  // Dual-write: append to legacy `content` AND to the parts[] streaming
  // text part in one set() so consumers stay consistent.
  set((s) =>
    _updateLastAssistant(s, (m) => {
      const withContent = { ...m, content: m.content + buffered };
      return _appendToStreamingText(withContent, buffered);
    }),
  );
}

function _clearTokenBuffer() {
  _tokenBuffer = "";
  if (_tokenFlushTimer) {
    clearTimeout(_tokenFlushTimer);
    _tokenFlushTimer = null;
  }
}

/**
 * Clear the flush timer, flush any buffered tokens, and finalize any
 * streaming text/reasoning parts on the last assistant message. Called from
 * all non-`done` stream exit paths (abort, network error, finally block)
 * so that `state: "streaming"` never leaks past stream teardown.
 */
function _flushAndFinalize(
  set: (fn: (s: AgentState) => Partial<AgentState>) => void,
) {
  if (_tokenFlushTimer) {
    clearTimeout(_tokenFlushTimer);
    _tokenFlushTimer = null;
  }
  _flushTokenBuffer(set);
  const now = Date.now();
  set((s) => _updateLastAssistant(s, (m) => _finalizeStreamingParts(m, now)));
}

// --- Parts helpers (AI Elements migration — Task 2) ---
// Exported for tests only — not intended as a public API.

export function _appendPart(msg: AgentMessage, part: MessagePart): AgentMessage {
  return { ...msg, parts: [...msg.parts, part] };
}

export function _updateLastMatchingPart(
  msg: AgentMessage,
  predicate: (p: MessagePart) => boolean,
  updater: (p: MessagePart) => MessagePart,
): AgentMessage {
  for (let i = msg.parts.length - 1; i >= 0; i--) {
    if (predicate(msg.parts[i])) {
      const next = [...msg.parts];
      next[i] = updater(msg.parts[i]);
      return { ...msg, parts: next };
    }
  }
  return msg;
}

export function _appendToStreamingText(
  msg: AgentMessage,
  delta: string,
): AgentMessage {
  const last = msg.parts.at(-1);
  if (last?.type === "text" && last.state === "streaming") {
    const next = [...msg.parts];
    next[next.length - 1] = { ...last, text: last.text + delta };
    return { ...msg, parts: next };
  }
  return _appendPart(msg, { type: "text", text: delta, state: "streaming" });
}

export function _appendToStreamingReasoning(
  msg: AgentMessage,
  delta: string,
  now: number,
): AgentMessage {
  const last = msg.parts.at(-1);
  if (last?.type === "reasoning" && last.state === "streaming") {
    const next = [...msg.parts];
    next[next.length - 1] = { ...last, text: last.text + delta };
    return { ...msg, parts: next };
  }
  return _appendPart(msg, {
    type: "reasoning",
    text: delta,
    state: "streaming",
    startedAt: now,
  });
}

export function _finalizeStreamingParts(
  msg: AgentMessage,
  now: number,
): AgentMessage {
  return {
    ...msg,
    parts: msg.parts.map((p) => {
      if (p.type === "text" && p.state === "streaming") {
        return { ...p, state: "done" as const };
      }
      if (p.type === "reasoning" && p.state === "streaming") {
        return { ...p, state: "done" as const, finishedAt: now };
      }
      return p;
    }),
  };
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
  sendMessage: (
    text: string,
    opts?: {
      intent?: string;
      intentArgs?: Record<string, unknown>;
      displayText?: string;
      attachments?: ChatImageAttachment[];
    },
  ) => Promise<void>;
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
  activeModel: DEFAULT_AI_MODEL,
  activeToolCalls: [],
  abortController: null,
  noteContext: null,

  sendMessage: async (
    text: string,
    opts?: {
      intent?: string;
      intentArgs?: Record<string, unknown>;
      displayText?: string;
      attachments?: ChatImageAttachment[];
    },
  ) => {
    const state = get();
    const attachments = opts?.attachments ?? [];
    const displayText = opts?.displayText ?? text;

    // Cancel existing stream if active (cancel + send behavior)
    if (state.isStreaming && state.abortController) {
      state.abortController.abort();
    }

    const userMsg: AgentMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: displayText,
      artifacts: [],
      relatedCards: [],
      gaps: [],
      toolCalls: [],
      plan: [],
      pendingApprovals: [],
      parts: [
        ...(displayText
          ? [{ type: "text" as const, text: displayText, state: "done" as const }]
          : []),
        ...attachments.map((attachment) => ({
          type: "image" as const,
          url: attachment.dataUrl,
          mimeType: attachment.mimeType,
          name: attachment.name,
          size: attachment.size,
          state: "done" as const,
        })),
      ],
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
      parts: [],
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

      const streamPayload = {
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
        attachments: attachments.map((attachment) => ({
          kind: attachment.kind,
          name: attachment.name,
          mime_type: attachment.mimeType,
          size: attachment.size,
          data_url: attachment.dataUrl,
        })),
        // Only send history if no thread (backend loads from DB when thread exists)
        history: state.activeThreadId
          ? undefined
          : selectOrderedMessages(state).slice(-20).map((m) => ({
              role: m.role,
              content: m.content,
            })),
        intent: opts?.intent,
        intent_args: opts?.intentArgs,
      };

      const aguiProjector = createAguiEventProjector();
      const handleAguiOrLegacyEvent = (
        event: string,
        data: Record<string, unknown>,
      ) => {
        for (const projected of aguiProjector.project(event, data)) {
          _handleSSEEvent(projected.event, projected.data, set);
        }
      };

      try {
        await streamSSE(
          apiRoutes.agent.streamV2,
          streamPayload,
          handleAguiOrLegacyEvent,
          composedSignal,
        );
      } catch (streamErr) {
        if (!isStreamV2Unavailable(streamErr)) throw streamErr;
        await streamSSE(
          apiRoutes.agent.stream,
          streamPayload,
          (event, data) => _handleSSEEvent(event, data, set),
          composedSignal,
        );
      }

      clearTimeout(timeoutId);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // User cancelled — expected. Still finalize streaming parts so the
        // UI doesn't get stuck with `state: "streaming"` forever.
        _flushAndFinalize(set);
      } else {
        // Flush any buffered tokens and finalize streaming parts before
        // setting the fallback error message.
        _flushAndFinalize(set);
        set((s) => _updateLastAssistant(s, (m) =>
          !m.content ? { ...m, content: "Sorry, something went wrong. Please try again." } : m,
        ));
      }
    } finally {
      // Defensive second pass: if `done` was received, this is cheap (no
      // streaming parts remain to update). If not, it guarantees finalize.
      _flushAndFinalize(set);
      set({ isStreaming: false, abortController: null });
    }
  },

  cancelStream: () => {
    const { abortController } = get();
    if (abortController) {
      abortController.abort();
      // Finalize before flipping streaming state so MessageBubble's
      // isAssistantStreaming flips false in the same render as isStreaming.
      _flushAndFinalize(set);
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
          // Hydrate parts[] from the DB (Task 4). Backend returns the canonical
          // AI Elements parts list when available; legacy rows (no `parts`
          // column value) fall back to [] and the UI synthesizes from legacy
          // fields via synthesizePartsFromLegacy.
          parts:
            (m as { parts?: MessagePart[] }).parts ??
            m.parts ??
            [],
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

function isStreamV2Unavailable(err: unknown): boolean {
  return err instanceof Error && /Stream failed:\s*404/.test(err.message);
}

// --- SSE event handler ---

function _handleSSEEvent(
  event: string,
  data: Record<string, unknown>,
  set: (fn: (s: AgentState) => Partial<AgentState>) => void,
) {
  notifyStreamCacheEvent(event, data);

  switch (event) {
    case "reasoning": {
      // Collapsible reasoning trace for o3/o4 models.
      // Dual-write: legacy `reasoning` string + streaming reasoning part.
      const delta = (data.content as string) || "";
      const now = Date.now();
      set((s) =>
        _updateLastAssistant(s, (m) => {
          const withReasoning = {
            ...m,
            reasoning:
              ((m as Record<string, unknown>).reasoning as string || "") + delta,
          };
          return _appendToStreamingReasoning(withReasoning, delta, now);
        }),
      );
      break;
    }

    case "token": {
      // _flushTokenBuffer handles the parts[] streaming text dual-write.
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
      const toolName = data.tool as string;
      const callId = (data.call_id as string | undefined) ?? "";
      const input = (data.args as Record<string, unknown>) || {};
      const now = Date.now();
      // Flush any pending buffered tokens so text finalizes before the
      // tool part appears (so "text → tool → text" produces 3 parts).
      if (_tokenFlushTimer) {
        clearTimeout(_tokenFlushTimer);
        _tokenFlushTimer = null;
      }
      _flushTokenBuffer(set);
      set((s) => ({
        activeToolCalls: [...s.activeToolCalls, toolCall],
        ..._updateLastAssistant(s, (m) => {
          const finalized = _finalizeStreamingParts(m, now);
          return _appendPart(finalized, {
            type: `tool-${toolName}` as UnknownToolPart["type"],
            toolCallId: callId,
            state: "input-available",
            input,
          });
        }),
      }));
      break;
    }

    case "plan": {
      const tasks = ((data.tasks as PlanTask[]) || []).map((task) => ({
        ...task,
        status: task.status || "queued",
      }));
      set((s) =>
        _updateLastAssistant(s, (m) => {
          let next = { ...m, plan: tasks };
          for (const task of tasks) {
            // Skip if a step with this taskId already exists.
            const existing = next.parts.find(
              (p) => p.type === "step" && p.taskId === task.id,
            );
            if (existing) continue;
            next = _appendPart(next, {
              type: "step",
              label: `${task.agent}: ${task.objective}`,
              state: "pending",
              taskId: task.id,
            });
          }
          return next;
        }),
      );
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
          const withPlan = { ...m, plan };
          const hasStep = withPlan.parts.some(
            (p) => p.type === "step" && p.taskId === taskId,
          );
          if (hasStep) {
            return _updateLastMatchingPart(
              withPlan,
              (p) => p.type === "step" && p.taskId === taskId,
              (p) =>
                p.type === "step" ? { ...p, state: "active" as const } : p,
            );
          }
          return _appendPart(withPlan, {
            type: "step",
            label: `${agent}: ${objective}`,
            state: "active",
            taskId,
          });
        }),
      );
      break;
    }

    case "task_done": {
      const taskId = data.task_id as string;
      set((s) =>
        _updateLastAssistant(s, (m) => {
          const withPlan = {
            ...m,
            plan: m.plan.map((task) =>
              task.id === taskId ? { ...task, status: "done" as const } : task,
            ),
          };
          const hasStep = withPlan.parts.some(
            (p) => p.type === "step" && p.taskId === taskId,
          );
          if (hasStep) {
            return _updateLastMatchingPart(
              withPlan,
              (p) => p.type === "step" && p.taskId === taskId,
              (p) =>
                p.type === "step" ? { ...p, state: "complete" as const } : p,
            );
          }
          return _appendPart(withPlan, {
            type: "step",
            label: taskId,
            state: "complete",
            taskId,
          });
        }),
      );
      break;
    }

    case "task_error": {
      const taskId = data.task_id as string;
      set((s) =>
        _updateLastAssistant(s, (m) => {
          const withPlan = {
            ...m,
            plan: m.plan.map((task) =>
              task.id === taskId ? { ...task, status: "error" as const } : task,
            ),
          };
          const hasStep = withPlan.parts.some(
            (p) => p.type === "step" && p.taskId === taskId,
          );
          if (hasStep) {
            return _updateLastMatchingPart(
              withPlan,
              (p) => p.type === "step" && p.taskId === taskId,
              (p) =>
                p.type === "step" ? { ...p, state: "error" as const } : p,
            );
          }
          return _appendPart(withPlan, {
            type: "step",
            label: taskId,
            state: "error",
            taskId,
          });
        }),
      );
      break;
    }

    case "tool_result": {
      const callId = data.call_id as string | undefined;
      const result = data.result as Record<string, unknown> | undefined;
      const hasError = !!(result && (result as { error?: unknown }).error);
      set((s) => {
        const tools = s.activeToolCalls.map((tc) =>
          (callId && tc.call_id === callId) || (!callId && tc.status === "pending")
            ? { ...tc, result: data.result as Record<string, unknown>, status: "done" as const }
            : tc,
        );
        return {
          activeToolCalls: tools,
          ..._updateLastAssistant(s, (m) => {
            const withTools = { ...m, toolCalls: [...tools] };
            return _updateLastMatchingPart(
              withTools,
              (p) =>
                typeof p.type === "string" &&
                p.type.startsWith("tool-") &&
                "toolCallId" in p &&
                (callId
                  ? (p as { toolCallId: string }).toolCallId === callId
                  : (p as { state: ToolState }).state === "input-available"),
              (p) => {
                if (!("toolCallId" in p)) return p;
                if (hasError) {
                  return {
                    ...p,
                    state: "output-error" as const,
                    errorText: String(
                      (result as { error: unknown }).error,
                    ),
                  } as MessagePart;
                }
                return {
                  ...p,
                  state: "output-available" as const,
                  output: result,
                } as MessagePart;
              },
            );
          }),
        };
      });
      break;
    }

    case "tool_end": {
      // Deprecated — tool_result covers this. No parts mutation.
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
      const message = (data.message as string) || "Something went wrong.";
      const now = Date.now();
      set((s) => ({
        ..._updateLastAssistant(s, (m) => {
          const withContent = { ...m, content: message };
          const finalized = _finalizeStreamingParts(withContent, now);
          return _appendPart(finalized, {
            type: "text",
            text: message,
            state: "done",
          });
        }),
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

    case "done": {
      // Flush any remaining buffered tokens.
      if (_tokenFlushTimer) {
        clearTimeout(_tokenFlushTimer);
        _tokenFlushTimer = null;
      }
      _flushTokenBuffer(set);
      // Finalize any still-streaming parts.
      const now = Date.now();
      set((s) =>
        _updateLastAssistant(s, (m) => _finalizeStreamingParts(m, now)),
      );
      break;
    }
  }
}
