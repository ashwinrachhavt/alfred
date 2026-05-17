import { describe, expect, it } from "vitest";

import { createAguiEventProjector } from "../agui-runtime";

describe("createAguiEventProjector", () => {
  it("maps AG-UI lifecycle and text events to the legacy agent store contract", () => {
    const projector = createAguiEventProjector();

    expect(
      projector.project("RUN_STARTED", {
        type: "RUN_STARTED",
        runId: "run-1",
        threadId: 42,
      }),
    ).toEqual([{ event: "thread_created", data: { thread_id: 42 } }]);

    expect(
      projector.project("TEXT_MESSAGE_CONTENT", {
        type: "TEXT_MESSAGE_CONTENT",
        messageId: "msg-1",
        delta: "Hello",
      }),
    ).toEqual([{ event: "token", data: { content: "Hello" } }]);

    expect(
      projector.project("RUN_FINISHED", {
        type: "RUN_FINISHED",
        runId: "run-1",
      }),
    ).toEqual([{ event: "done", data: { run_id: "run-1" } }]);
  });

  it("buffers AG-UI tool args until TOOL_CALL_END then emits tool_start", () => {
    const projector = createAguiEventProjector();

    expect(
      projector.project("TOOL_CALL_START", {
        type: "TOOL_CALL_START",
        toolCallId: "call-1",
        toolCallName: "search_kb",
      }),
    ).toEqual([]);

    expect(
      projector.project("TOOL_CALL_ARGS", {
        type: "TOOL_CALL_ARGS",
        toolCallId: "call-1",
        delta: '{"q":"epistemology"}',
      }),
    ).toEqual([]);

    expect(
      projector.project("TOOL_CALL_END", {
        type: "TOOL_CALL_END",
        toolCallId: "call-1",
      }),
    ).toEqual([
      {
        event: "tool_start",
        data: {
          call_id: "call-1",
          tool: "search_kb",
          args: { q: "epistemology" },
        },
      },
    ]);
  });

  it("maps AG-UI tool results to legacy tool_result events", () => {
    const projector = createAguiEventProjector();

    expect(
      projector.project("TOOL_CALL_RESULT", {
        type: "TOOL_CALL_RESULT",
        toolCallId: "call-1",
        messageId: "msg-1",
        role: "tool",
        content: '{"hits":["z1"]}',
      }),
    ).toEqual([
      {
        event: "tool_result",
        data: {
          call_id: "call-1",
          result: { hits: ["z1"] },
        },
      },
    ]);
  });

  it("maps AG-UI state JSON patches to reactive artifact and related-card events", () => {
    const projector = createAguiEventProjector();
    const artifact = {
      type: "zettel",
      action: "created",
      zettel: { id: 7, title: "Knowledge", summary: "", tags: [] },
    };
    const related = [{ zettelId: 11, title: "Adjacent", domain: "systems" }];

    expect(
      projector.project("STATE_DELTA", {
        type: "STATE_DELTA",
        delta: [{ op: "add", path: "/artifacts/-", value: artifact }],
      }),
    ).toEqual([{ event: "artifact", data: artifact }]);

    expect(
      projector.project("STATE_DELTA", {
        type: "STATE_DELTA",
        delta: [{ op: "add", path: "/relatedCards", value: related }],
      }),
    ).toEqual([{ event: "related", data: { cards: related } }]);
  });

  it("maps AG-UI reasoning events to the reasoning stream", () => {
    const projector = createAguiEventProjector();

    expect(
      projector.project("REASONING_MESSAGE_CONTENT", {
        type: "REASONING_MESSAGE_CONTENT",
        messageId: "msg-1::reasoning",
        delta: "Checking assumptions.",
      }),
    ).toEqual([
      {
        event: "reasoning",
        data: { content: "Checking assumptions." },
      },
    ]);
  });

  it("maps Alfred zettel custom events back to zettel stream events", () => {
    const projector = createAguiEventProjector();

    expect(
      projector.project("CUSTOM", {
        type: "CUSTOM",
        name: "alfred.zettel.card_saved",
        value: { id: 12, title: "Atomicity" },
      }),
    ).toEqual([
      {
        event: "card_saved",
        data: { id: 12, title: "Atomicity" },
      },
    ]);
  });
});
