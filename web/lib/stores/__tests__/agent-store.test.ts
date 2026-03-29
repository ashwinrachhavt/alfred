import { describe, it, expect, beforeEach, vi } from "vitest";

// Mock dependencies BEFORE importing the store
vi.mock("@/lib/api/client", () => ({
  apiFetch: vi.fn().mockResolvedValue([]),
}));

vi.mock("@/lib/api/sse", () => ({
  streamSSE: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/lib/api/routes", () => ({
  apiRoutes: {
    agent: {
      stream: "/api/agent/stream",
      threads: "/api/agent/threads",
      threadById: (id: number) => `/api/agent/threads/${id}`,
    },
  },
}));

import { useAgentStore, type NoteContext } from "../agent-store";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resetStore() {
  useAgentStore.setState({
    messages: [],
    threads: [],
    activeThreadId: null,
    isStreaming: false,
    activeLens: null,
    activeModel: "gpt-5.4",
    activeToolCalls: [],
    abortController: null,
    noteContext: null,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  resetStore();
});

describe("agent-store initial state", () => {
  it("has correct defaults", () => {
    const state = useAgentStore.getState();
    expect(state.messages).toEqual([]);
    expect(state.threads).toEqual([]);
    expect(state.activeThreadId).toBeNull();
    expect(state.isStreaming).toBe(false);
    expect(state.activeLens).toBeNull();
    expect(state.activeModel).toBe("gpt-5.4");
    expect(state.activeToolCalls).toEqual([]);
    expect(state.abortController).toBeNull();
    expect(state.noteContext).toBeNull();
  });
});

describe("setNoteContext", () => {
  it("sets noteContext and clears messages", () => {
    // Seed some existing state
    useAgentStore.setState({
      messages: [
        {
          id: "user-1",
          role: "user",
          content: "old message",
          artifacts: [],
          relatedCards: [],
          gaps: [],
          toolCalls: [],
          timestamp: Date.now(),
        },
      ],
      activeThreadId: 42,
    });

    const ctx: NoteContext = {
      noteId: "note-abc",
      title: "My Note",
      contentPreview: "Some content...",
    };

    useAgentStore.getState().setNoteContext(ctx);

    const state = useAgentStore.getState();
    expect(state.noteContext).toEqual(ctx);
    expect(state.messages).toEqual([]);
    expect(state.activeThreadId).toBeNull();
    expect(state.isStreaming).toBe(false);
    expect(state.activeToolCalls).toEqual([]);
  });

  it("clears noteContext when passed null", () => {
    useAgentStore.setState({
      noteContext: { noteId: "n1", title: "T", contentPreview: "P" },
    });

    useAgentStore.getState().setNoteContext(null);

    expect(useAgentStore.getState().noteContext).toBeNull();
  });
});

describe("clearMessages", () => {
  it("resets messages, activeThreadId, and noteContext", () => {
    useAgentStore.setState({
      messages: [
        {
          id: "u1",
          role: "user",
          content: "hi",
          artifacts: [],
          relatedCards: [],
          gaps: [],
          toolCalls: [],
          timestamp: Date.now(),
        },
      ],
      activeThreadId: 7,
      noteContext: { noteId: "n", title: "T", contentPreview: "" },
    });

    useAgentStore.getState().clearMessages();

    const state = useAgentStore.getState();
    expect(state.messages).toEqual([]);
    expect(state.activeThreadId).toBeNull();
    expect(state.noteContext).toBeNull();
  });
});

describe("setLens / setModel", () => {
  it("sets the active lens", () => {
    useAgentStore.getState().setLens("socratic");
    expect(useAgentStore.getState().activeLens).toBe("socratic");
  });

  it("clears the active lens with null", () => {
    useAgentStore.setState({ activeLens: "stoic" });
    useAgentStore.getState().setLens(null);
    expect(useAgentStore.getState().activeLens).toBeNull();
  });

  it("sets the active model", () => {
    useAgentStore.getState().setModel("o3");
    expect(useAgentStore.getState().activeModel).toBe("o3");
  });
});

describe("_handleSSEEvent via setState simulation", () => {
  // We can't call _handleSSEEvent directly (it's module-private),
  // but we can verify the state shape that gaps events produce.
  it("gaps event updates the last assistant message's gaps", () => {
    // Set up a conversation with an assistant message
    useAgentStore.setState({
      messages: [
        {
          id: "u1",
          role: "user",
          content: "explain monads",
          artifacts: [],
          relatedCards: [],
          gaps: [],
          toolCalls: [],
          timestamp: Date.now(),
        },
        {
          id: "a1",
          role: "assistant",
          content: "A monad is...",
          artifacts: [],
          relatedCards: [],
          gaps: [],
          toolCalls: [],
          timestamp: Date.now(),
        },
      ],
    });

    // Simulate what _handleSSEEvent("gaps", ...) does internally
    const gapData = [
      { concept: "functors", description: "Pre-requisite for monads", confidence: 0.8 },
      { concept: "applicatives", description: "Between functor and monad", confidence: 0.6 },
    ];

    useAgentStore.setState((s) => {
      const msgs = s.messages.map((m, i) =>
        i === s.messages.length - 1 && m.role === "assistant"
          ? { ...m, gaps: gapData }
          : m,
      );
      return { messages: msgs };
    });

    const state = useAgentStore.getState();
    const lastMsg = state.messages[state.messages.length - 1];
    expect(lastMsg.gaps).toHaveLength(2);
    expect(lastMsg.gaps[0].concept).toBe("functors");
    expect(lastMsg.gaps[1].concept).toBe("applicatives");

    // First message should be untouched
    expect(state.messages[0].gaps).toEqual([]);
  });
});

describe("cancelStream", () => {
  it("aborts the controller and resets streaming state", () => {
    const controller = new AbortController();
    const abortSpy = vi.spyOn(controller, "abort");

    useAgentStore.setState({
      isStreaming: true,
      abortController: controller,
    });

    useAgentStore.getState().cancelStream();

    expect(abortSpy).toHaveBeenCalled();
    expect(useAgentStore.getState().isStreaming).toBe(false);
    expect(useAgentStore.getState().abortController).toBeNull();
  });

  it("does nothing when not streaming", () => {
    useAgentStore.setState({ isStreaming: false, abortController: null });
    // Should not throw
    useAgentStore.getState().cancelStream();
    expect(useAgentStore.getState().isStreaming).toBe(false);
  });
});
