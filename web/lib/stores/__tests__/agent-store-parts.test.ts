import { describe, it, expect, vi } from "vitest";

// Mock dependencies BEFORE importing the store (matches agent-store.test.ts).
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
  _appendPart,
  _appendToStreamingText,
  _appendToStreamingReasoning,
  _finalizeStreamingParts,
  _updateLastMatchingPart,
  type AgentMessage,
  type MessagePart,
} from "../agent-store";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMessage(overrides: Partial<AgentMessage> = {}): AgentMessage {
  return {
    id: "assistant-1",
    role: "assistant",
    content: "",
    artifacts: [],
    relatedCards: [],
    gaps: [],
    toolCalls: [],
    plan: [],
    pendingApprovals: [],
    parts: [],
    timestamp: 0,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("_appendToStreamingText", () => {
  it("appends to a trailing streaming text part rather than creating a new one", () => {
    const msg = makeMessage({
      parts: [{ type: "text", text: "Hello ", state: "streaming" }],
    });

    const next = _appendToStreamingText(msg, "world");

    expect(next.parts).toHaveLength(1);
    expect(next.parts[0]).toEqual({
      type: "text",
      text: "Hello world",
      state: "streaming",
    });
  });

  it("creates a new streaming text part when the last part is not streaming text", () => {
    const msg = makeMessage({
      parts: [{ type: "text", text: "Done.", state: "done" }],
    });

    const next = _appendToStreamingText(msg, "Next thought");

    expect(next.parts).toHaveLength(2);
    expect(next.parts[1]).toEqual({
      type: "text",
      text: "Next thought",
      state: "streaming",
    });
  });

  it("creates a new streaming text part when the last part is a tool part", () => {
    const msg = makeMessage({
      parts: [
        {
          type: "tool-search_kb",
          toolCallId: "call-1",
          state: "output-available",
          input: { q: "monads" },
          output: { results: [] },
        },
      ],
    });

    const next = _appendToStreamingText(msg, "Here are the results.");

    expect(next.parts).toHaveLength(2);
    expect(next.parts[1]).toEqual({
      type: "text",
      text: "Here are the results.",
      state: "streaming",
    });
  });

  it("creates a new part when parts[] is empty", () => {
    const msg = makeMessage();

    const next = _appendToStreamingText(msg, "First");

    expect(next.parts).toHaveLength(1);
    expect(next.parts[0]).toEqual({
      type: "text",
      text: "First",
      state: "streaming",
    });
  });
});

describe("_appendToStreamingReasoning", () => {
  it("sets startedAt on the new part and preserves it across deltas", () => {
    const t0 = 1000;
    const t1 = 1500;
    let msg = makeMessage();

    msg = _appendToStreamingReasoning(msg, "Let me think.", t0);
    expect(msg.parts).toHaveLength(1);
    expect(msg.parts[0]).toEqual({
      type: "reasoning",
      text: "Let me think.",
      state: "streaming",
      startedAt: t0,
    });

    msg = _appendToStreamingReasoning(msg, " More thought.", t1);
    expect(msg.parts).toHaveLength(1);
    expect(msg.parts[0]).toEqual({
      type: "reasoning",
      text: "Let me think. More thought.",
      state: "streaming",
      startedAt: t0, // preserved — startedAt is anchored to the first delta
    });
  });

  it("creates a new reasoning part when the last part is not streaming reasoning", () => {
    const msg = makeMessage({
      parts: [{ type: "text", text: "hi", state: "streaming" }],
    });

    const next = _appendToStreamingReasoning(msg, "new thought", 42);

    expect(next.parts).toHaveLength(2);
    expect(next.parts[1]).toMatchObject({
      type: "reasoning",
      text: "new thought",
      state: "streaming",
      startedAt: 42,
    });
  });
});

describe("_finalizeStreamingParts", () => {
  it("transitions streaming text to done and streaming reasoning to done with finishedAt", () => {
    const now = 9999;
    const msg = makeMessage({
      parts: [
        { type: "reasoning", text: "hmm", state: "streaming", startedAt: 100 },
        { type: "text", text: "answer", state: "streaming" },
        { type: "text", text: "already closed", state: "done" },
      ],
    });

    const next = _finalizeStreamingParts(msg, now);

    expect(next.parts[0]).toEqual({
      type: "reasoning",
      text: "hmm",
      state: "done",
      startedAt: 100,
      finishedAt: now,
    });
    expect(next.parts[1]).toEqual({
      type: "text",
      text: "answer",
      state: "done",
    });
    // Already-done parts stay untouched.
    expect(next.parts[2]).toEqual({
      type: "text",
      text: "already closed",
      state: "done",
    });
  });

  it("leaves tool and step parts untouched", () => {
    const toolPart: MessagePart = {
      type: "tool-search_kb",
      toolCallId: "c1",
      state: "output-available",
      input: {},
      output: {},
    };
    const stepPart: MessagePart = {
      type: "step",
      label: "knowledge: search",
      state: "active",
      taskId: "t1",
    };
    const msg = makeMessage({ parts: [toolPart, stepPart] });

    const next = _finalizeStreamingParts(msg, 1);

    expect(next.parts).toEqual([toolPart, stepPart]);
  });
});

describe("_updateLastMatchingPart", () => {
  it("updates the latest matching part and leaves earlier matches alone", () => {
    const msg = makeMessage({
      parts: [
        {
          type: "tool-search_kb",
          toolCallId: "c1",
          state: "output-available",
          input: { q: "a" },
          output: { r: 1 },
        },
        {
          type: "tool-search_kb",
          toolCallId: "c2",
          state: "input-available",
          input: { q: "b" },
        },
      ],
    });

    const next = _updateLastMatchingPart(
      msg,
      (p) => p.type === "tool-search_kb",
      (p) =>
        p.type === "tool-search_kb"
          ? { ...p, state: "output-available" as const, output: { r: 2 } }
          : p,
    );

    // First matching part is untouched.
    expect(next.parts[0]).toEqual({
      type: "tool-search_kb",
      toolCallId: "c1",
      state: "output-available",
      input: { q: "a" },
      output: { r: 1 },
    });
    // Latest match is updated.
    expect(next.parts[1]).toEqual({
      type: "tool-search_kb",
      toolCallId: "c2",
      state: "output-available",
      input: { q: "b" },
      output: { r: 2 },
    });
  });

  it("returns the message unchanged when no part matches", () => {
    const msg = makeMessage({
      parts: [{ type: "text", text: "hi", state: "done" }],
    });

    const next = _updateLastMatchingPart(
      msg,
      (p) => p.type === "reasoning",
      (p) => p,
    );

    expect(next).toBe(msg);
  });
});

describe("text -> tool -> text produces 3 parts (edge case)", () => {
  // Simulates the order of operations that the tool_start SSE case performs:
  //   1. Finalize streaming parts (so in-flight text closes).
  //   2. Append the tool part.
  // Then a subsequent token flush should open a *new* streaming text part,
  // not re-enter the now-finalized one.
  it("finalizes prior streaming text before the tool part so a later token opens a new part", () => {
    let msg = makeMessage();

    // Phase 1: stream some text.
    msg = _appendToStreamingText(msg, "Hello ");
    msg = _appendToStreamingText(msg, "there.");
    expect(msg.parts).toHaveLength(1);
    expect(msg.parts[0]).toMatchObject({ type: "text", state: "streaming" });

    // Phase 2: tool_start — finalize streaming parts, then append tool.
    msg = _finalizeStreamingParts(msg, 100);
    msg = _appendPart(msg, {
      type: "tool-search_kb",
      toolCallId: "c1",
      state: "input-available",
      input: { q: "monads" },
    });

    // Phase 3: tokens resume after the tool result.
    msg = _appendToStreamingText(msg, "Here is the answer.");

    expect(msg.parts).toHaveLength(3);
    expect(msg.parts[0]).toMatchObject({ type: "text", state: "done" });
    expect(msg.parts[1]).toMatchObject({ type: "tool-search_kb" });
    expect(msg.parts[2]).toMatchObject({
      type: "text",
      text: "Here is the answer.",
      state: "streaming",
    });
  });
});
