import { create } from "zustand";
import { useShallow } from "zustand/react/shallow";

import { streamSSE } from "@/lib/api/sse";

// --- Types ---------------------------------------------------------------

export type Todo = {
  status: "pending" | "in_progress" | "completed";
  content: string;
};

export type DeepToolCall = {
  callId: string;
  tool: string;
  args: Record<string, unknown>;
  result?: Record<string, unknown>;
  subagent?: string | null;
  status: "pending" | "done" | "error";
};

export type SubagentLane = {
  name: string;
  tokens: string;
  toolCalls: DeepToolCall[];
  lastActivityAt: number;
};

export type FileArtifact = {
  path: string;
  bytes: number;
  content?: string;
  updatedAt: number;
};

export type RunState = "idle" | "streaming" | "done" | "error";

export type RunRequestBody = {
  topic: string;
  agent_spec_id?: number;
  inline_spec?: unknown;
  thread_id?: number;
};

type ResearchState = {
  runState: RunState;
  error: string | null;

  // Plan (orchestrator todos)
  todos: Todo[];

  // Main orchestrator output
  mainTokens: string;
  mainToolCalls: DeepToolCall[];

  // Subagent activity indexed by subagent name
  subagents: Record<string, SubagentLane>;

  // Files written by the agent (virtual filesystem)
  files: Record<string, FileArtifact>;

  // Abort control
  abort: AbortController | null;
};

type ResearchActions = {
  startRun: (body: RunRequestBody) => Promise<void>;
  cancel: () => void;
  reset: () => void;
};

const initialState: ResearchState = {
  runState: "idle",
  error: null,
  todos: [],
  mainTokens: "",
  mainToolCalls: [],
  subagents: {},
  files: {},
  abort: null,
};

export const useResearchStore = create<ResearchState & ResearchActions>()((set, get) => ({
  ...initialState,

  reset: () => set({ ...initialState }),

  cancel: () => {
    const { abort } = get();
    if (abort) abort.abort();
    set({ runState: "idle", abort: null });
  },

  startRun: async (body) => {
    get().cancel();

    const abort = new AbortController();
    set({
      ...initialState,
      runState: "streaming",
      abort,
    });

    try {
      await streamSSE(
        "/api/research/run",
        body as unknown as Record<string, unknown>,
        (event, data) => handleEvent(set, get, event, data),
        abort.signal,
      );
      if (get().runState === "streaming") set({ runState: "done", abort: null });
    } catch (err) {
      if ((err as Error)?.name === "AbortError") return;
      set({
        runState: "error",
        error: err instanceof Error ? err.message : "Stream failed",
        abort: null,
      });
    }
  },
}));

// --- Event routing -------------------------------------------------------

function handleEvent(
  set: (
    partial:
      | Partial<ResearchState>
      | ((s: ResearchState) => Partial<ResearchState>),
  ) => void,
  _get: () => ResearchState & ResearchActions,
  event: string,
  data: Record<string, unknown>,
): void {
  switch (event) {
    case "plan": {
      const todos = (data.todos as Todo[]) ?? [];
      set({ todos });
      return;
    }

    case "token": {
      const content = (data.content as string) ?? "";
      if (!content) return;
      set((s) => ({ mainTokens: s.mainTokens + content }));
      return;
    }

    case "subagent_msg": {
      const sub = (data.subagent as string | null) ?? "unknown";
      const content = (data.content as string) ?? "";
      if (!content) return;
      set((s) => ({
        subagents: {
          ...s.subagents,
          [sub]: {
            name: sub,
            tokens: (s.subagents[sub]?.tokens ?? "") + content,
            toolCalls: s.subagents[sub]?.toolCalls ?? [],
            lastActivityAt: Date.now(),
          },
        },
      }));
      return;
    }

    case "tool_start": {
      const tc: DeepToolCall = {
        callId: (data.call_id as string) ?? String(Date.now()),
        tool: (data.tool as string) ?? "?",
        args: (data.args as Record<string, unknown>) ?? {},
        subagent: (data.subagent as string | null) ?? null,
        status: "pending",
      };
      if (tc.subagent) {
        const sub = tc.subagent;
        set((s) => ({
          subagents: {
            ...s.subagents,
            [sub]: {
              name: sub,
              tokens: s.subagents[sub]?.tokens ?? "",
              toolCalls: [...(s.subagents[sub]?.toolCalls ?? []), tc],
              lastActivityAt: Date.now(),
            },
          },
        }));
      } else {
        set((s) => ({ mainToolCalls: [...s.mainToolCalls, tc] }));
      }
      return;
    }

    case "tool_result": {
      const callId = (data.call_id as string) ?? "";
      const result = (data.result as Record<string, unknown>) ?? {};
      const patchList = (list: DeepToolCall[]): DeepToolCall[] =>
        list.map((tc) =>
          tc.callId === callId ? { ...tc, status: "done", result } : tc,
        );
      set((s) => ({
        mainToolCalls: patchList(s.mainToolCalls),
        subagents: Object.fromEntries(
          Object.entries(s.subagents).map(([k, lane]) => [
            k,
            { ...lane, toolCalls: patchList(lane.toolCalls) },
          ]),
        ),
      }));
      return;
    }

    case "file_write": {
      const path = (data.path as string) ?? "";
      const bytes = (data.bytes as number) ?? 0;
      set((s) => ({
        files: {
          ...s.files,
          [path]: {
            path,
            bytes,
            content: s.files[path]?.content,
            updatedAt: Date.now(),
          },
        },
      }));
      return;
    }

    case "task_start": {
      // Node boundary event; non-critical for the happy path.
      return;
    }

    case "done": {
      const finalFiles = (data.final_files as Record<string, string>) ?? {};
      set((s) => {
        const merged = { ...s.files };
        for (const [path, content] of Object.entries(finalFiles)) {
          merged[path] = {
            path,
            bytes: content.length,
            content,
            updatedAt: Date.now(),
          };
        }
        return { files: merged, runState: "done", abort: null };
      });
      return;
    }

    case "error": {
      set({
        runState: "error",
        error: (data.message as string) ?? "Unknown error",
        abort: null,
      });
      return;
    }

    default:
      // Unknown events (e.g. custom) are dropped silently.
      return;
  }
}

// --- Selector hooks -------------------------------------------------------

export function useResearchRunState() {
  return useResearchStore(
    useShallow((s) => ({
      runState: s.runState,
      error: s.error,
      isStreaming: s.runState === "streaming",
    })),
  );
}

export function useResearchPlan() {
  return useResearchStore((s) => s.todos);
}

export function useResearchMainStream() {
  return useResearchStore(
    useShallow((s) => ({
      tokens: s.mainTokens,
      toolCalls: s.mainToolCalls,
    })),
  );
}

export function useResearchSubagents() {
  return useResearchStore((s) => s.subagents);
}

export function useResearchFiles() {
  return useResearchStore((s) => s.files);
}

export function useResearchActions() {
  return useResearchStore(
    useShallow((s) => ({
      startRun: s.startRun,
      cancel: s.cancel,
      reset: s.reset,
    })),
  );
}
