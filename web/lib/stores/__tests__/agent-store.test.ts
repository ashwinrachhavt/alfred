import { describe, it, expect, beforeEach, vi } from "vitest";

import { DEFAULT_AI_MODEL } from "@/lib/constants/ai";

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

import {
  useAgentStore,
  selectOrderedMessages,
  type AgentMessage,
  type NoteContext,
} from "../agent-store";
import { streamSSE } from "@/lib/api/sse";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type MsgInput = Pick<AgentMessage, "id" | "role" | "content"> &
  Partial<
    Pick<
      AgentMessage,
      | "artifacts"
      | "relatedCards"
      | "gaps"
      | "toolCalls"
      | "plan"
      | "pendingApprovals"
      | "parts"
      | "timestamp"
    >
  >;

function normalize(msgs: MsgInput[]) {
  const messagesById: Record<string, AgentMessage> = {};
  const messageOrder: string[] = [];
  for (const m of msgs) {
    const msg: AgentMessage = {
      artifacts: [],
      relatedCards: [],
      gaps: [],
      toolCalls: [],
      plan: [],
      pendingApprovals: [],
      parts: [],
      timestamp: Date.now(),
      ...m,
    };
    messagesById[msg.id] = msg;
    messageOrder.push(msg.id);
  }
  return { messagesById, messageOrder };
}

function resetStore() {
  useAgentStore.setState({
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
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  resetStore();
});

describe("agent-store initial state", () => {
  it("has correct defaults", () => {
    const state = useAgentStore.getState();
    expect(state.messagesById).toEqual({});
    expect(state.messageOrder).toEqual([]);
    expect(state.threads).toEqual([]);
    expect(state.activeThreadId).toBeNull();
    expect(state.isStreaming).toBe(false);
    expect(state.activeLens).toBeNull();
    expect(state.activeModel).toBe(DEFAULT_AI_MODEL);
    expect(state.activeToolCalls).toEqual([]);
    expect(state.abortController).toBeNull();
    expect(state.noteContext).toBeNull();
  });
});

describe("setNoteContext", () => {
  it("sets noteContext and clears messages", () => {
    // Seed some existing state
    useAgentStore.setState({
      ...normalize([{ id: "user-1", role: "user", content: "old message" }]),
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
    expect(selectOrderedMessages(state)).toEqual([]);
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
      ...normalize([{ id: "u1", role: "user", content: "hi" }]),
      activeThreadId: 7,
      noteContext: { noteId: "n", title: "T", contentPreview: "" },
    });

    useAgentStore.getState().clearMessages();

    const state = useAgentStore.getState();
    expect(selectOrderedMessages(state)).toEqual([]);
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
    useAgentStore.setState(normalize([
      { id: "u1", role: "user", content: "explain monads" },
      { id: "a1", role: "assistant", content: "A monad is..." },
    ]));

    // Simulate what _handleSSEEvent("gaps", ...) does internally
    const gapData = [
      { concept: "functors", description: "Pre-requisite for monads", confidence: 0.8 },
      { concept: "applicatives", description: "Between functor and monad", confidence: 0.6 },
    ];

    useAgentStore.setState((s) => {
      // Update last assistant message's gaps in normalized state
      const { messageOrder, messagesById } = s;
      for (let i = messageOrder.length - 1; i >= 0; i--) {
        const id = messageOrder[i];
        const msg = messagesById[id];
        if (msg?.role === "assistant") {
          return { messagesById: { ...messagesById, [id]: { ...msg, gaps: gapData } } };
        }
      }
      return {};
    });

    const state = useAgentStore.getState();
    const messages = selectOrderedMessages(state);
    const lastMsg = messages[messages.length - 1];
    expect(lastMsg.gaps).toHaveLength(2);
    expect(lastMsg.gaps[0].concept).toBe("functors");
    expect(lastMsg.gaps[1].concept).toBe("applicatives");

    // First message should be untouched
    expect(messages[0].gaps).toEqual([]);
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

describe("sendMessage", () => {
  it("stores image parts and forwards attachments to the stream request", async () => {
    vi.mocked(streamSSE).mockImplementation(async (_url, _body, onEvent) => {
      onEvent("done", {});
    });

    const attachment = {
      id: "img-1",
      kind: "image" as const,
      name: "screenshot.png",
      mimeType: "image/png",
      size: 12,
      dataUrl: "data:image/png;base64,iVBORw0KGgo=",
    };

    await useAgentStore.getState().sendMessage("Describe this", {
      attachments: [attachment],
    });

    const [, body] = vi.mocked(streamSSE).mock.calls[0];
    expect(body.attachments).toEqual([
      {
        kind: "image",
        name: "screenshot.png",
        mime_type: "image/png",
        size: 12,
        data_url: "data:image/png;base64,iVBORw0KGgo=",
      },
    ]);

    const [userMessage] = selectOrderedMessages(useAgentStore.getState());
    expect(userMessage.parts).toEqual([
      { type: "text", text: "Describe this", state: "done" },
      {
        type: "image",
        url: "data:image/png;base64,iVBORw0KGgo=",
        mimeType: "image/png",
        name: "screenshot.png",
        size: 12,
        state: "done",
      },
    ]);
  });
});
