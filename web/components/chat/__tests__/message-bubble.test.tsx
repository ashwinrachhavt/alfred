import type { ComponentType, ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "@/lib/api/client";
import type { AgentMessage, MessagePart, ToolCall } from "@/lib/stores/agent-store";

const { copyTextToClipboard } = vi.hoisted(() => ({
  copyTextToClipboard: vi.fn(),
}));

vi.mock("@/components/agent/artifact-card", () => ({
  ArtifactCardComponent: ({ artifact }: { artifact: { title: string } }) => (
    <div data-testid="artifact-card">{artifact.title}</div>
  ),
}));

vi.mock("@/components/agent/related-cards", () => ({
  RelatedCards: () => <div data-testid="related-cards" />,
}));

vi.mock("@/components/agent/insight-to-card", () => ({
  InsightToCard: ({ children }: { children: ReactNode }) => (
    <div data-testid="insight-to-card">{children}</div>
  ),
}));

// AI Elements depend on Streamdown (ESM) which is heavy in jsdom; stub to
// simple passthrough renderers that preserve content so assertions work.
vi.mock("@/components/ai-elements/message", () => ({
  Message: ({ children }: { children: ReactNode }) => (
    <div data-testid="ai-message">{children}</div>
  ),
  MessageContent: ({ children }: { children: ReactNode }) => (
    <div data-testid="ai-message-content">{children}</div>
  ),
  MessageResponse: ({ children }: { children: string }) => (
    <div data-testid="ai-message-response">{children}</div>
  ),
}));

vi.mock("@/components/ai-elements/reasoning", () => ({
  Reasoning: ({
    children,
    isStreaming,
    duration,
  }: {
    children: ReactNode;
    isStreaming?: boolean;
    duration?: number;
  }) => (
    <div
      data-testid="ai-reasoning"
      data-streaming={isStreaming ? "true" : "false"}
      data-duration={String(duration ?? "")}
    >
      {children}
    </div>
  ),
  ReasoningTrigger: () => <button type="button">Thinking</button>,
  ReasoningContent: ({ children }: { children: string }) => (
    <div data-testid="ai-reasoning-content">{children}</div>
  ),
}));

vi.mock("@/components/ai-elements/tool", () => ({
  Tool: ({
    children,
    open,
    defaultOpen,
  }: {
    children: ReactNode;
    open?: boolean;
    defaultOpen?: boolean;
  }) => (
    <div
      data-testid="ai-tool"
      data-open={String(open ?? defaultOpen ?? false)}
    >
      {children}
    </div>
  ),
  ToolHeader: ({ type, state }: { type: string; state: string }) => (
    <div data-testid="ai-tool-header">
      {type.replace(/^tool-/, "").replace(/_/g, " ")} · {state}
    </div>
  ),
  ToolContent: ({ children }: { children: ReactNode }) => (
    <div data-testid="ai-tool-content">{children}</div>
  ),
  ToolInput: ({ input }: { input: unknown }) => (
    <div data-testid="ai-tool-input">{JSON.stringify(input)}</div>
  ),
  ToolOutput: ({ output, errorText }: { output?: unknown; errorText?: string }) => (
    <div data-testid="ai-tool-output">
      {errorText ?? (output ? JSON.stringify(output) : "")}
    </div>
  ),
}));

vi.mock("@/components/ai-elements/chain-of-thought", () => ({
  ChainOfThought: ({ children }: { children: ReactNode }) => (
    <div data-testid="ai-chain-of-thought">{children}</div>
  ),
  ChainOfThoughtStep: ({
    label,
    description,
    status,
    icon: Icon,
    className,
  }: {
    label: ReactNode;
    description?: ReactNode;
    status?: string;
    icon?: ComponentType<{ "data-testid"?: string }>;
    className?: string;
  }) => (
    <div
      data-testid="ai-chain-step"
      data-status={status}
      data-description={typeof description === "string" ? description : ""}
      data-classname={className ?? ""}
    >
      {Icon ? <Icon data-testid="ai-chain-step-icon" /> : null}
      <span>{label}</span>
      {description ? <span>{description}</span> : null}
    </div>
  ),
}));

vi.mock("@/lib/api/client", () => ({
  apiFetch: vi.fn(),
}));

vi.mock("@/lib/clipboard", () => ({
  copyTextToClipboard,
}));

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
  },
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(" "),
}));

import { MessageBubble } from "../message-bubble";

function makeMessage(overrides: Partial<AgentMessage> = {}): AgentMessage {
  return {
    id: "test-1",
    role: "assistant",
    content: "Hello world",
    artifacts: [],
    relatedCards: [],
    gaps: [],
    toolCalls: [],
    plan: [],
    pendingApprovals: [],
    parts: [],
    timestamp: Date.now(),
    ...overrides,
  };
}

describe("MessageBubble", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    copyTextToClipboard.mockResolvedValue(undefined);
  });

  it("renders user message as right-aligned bubble", () => {
    const message = makeMessage({ role: "user", content: "My question" });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.getByText("My question")).toBeInTheDocument();
  });

  it("renders assistant message with markdown content", () => {
    const message = makeMessage({ content: "Test response" });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    // Post-stream rendering uses CommentableMarkdownBlock -> MessageResponse.
    expect(screen.getByTestId("ai-message-response")).toBeInTheDocument();
    expect(screen.getByText("Test response")).toBeInTheDocument();
  });

  it("shows reasoning trace when reasoning exists (via parts[])", () => {
    const parts: MessagePart[] = [
      {
        type: "reasoning",
        text: "Let me think about this...",
        state: "done",
        startedAt: 0,
        finishedAt: 1000,
      },
    ];
    const message = makeMessage({
      reasoning: "Let me think about this...",
      parts,
    });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.getByTestId("ai-reasoning")).toBeInTheDocument();
    expect(screen.getByText("Thinking")).toBeInTheDocument();
  });

  it("renders reasoning from legacy `reasoning` field via synthesis", () => {
    // Message with no parts[] (e.g., historical DB row).
    const message = makeMessage({
      reasoning: "Deep thoughts here",
      parts: [],
    });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.getByTestId("ai-reasoning")).toBeInTheDocument();
    expect(screen.getByTestId("ai-reasoning-content")).toHaveTextContent(
      "Deep thoughts here",
    );
  });

  it("does not show reasoning section when reasoning is absent", () => {
    const message = makeMessage({ reasoning: undefined });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.queryByTestId("ai-reasoning")).not.toBeInTheDocument();
  });

  it("shows tool calls via AI Elements Tool primitive", () => {
    const toolCalls: ToolCall[] = [
      { tool: "search_kb", args: {}, status: "pending" },
      { tool: "create_zettel", args: {}, status: "done", call_id: "c1" },
    ];
    const message = makeMessage({ toolCalls });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    const headers = screen.getAllByTestId("ai-tool-header");
    expect(headers).toHaveLength(2);
    expect(headers[0]).toHaveTextContent("search kb");
    expect(headers[1]).toHaveTextContent("create zettel");
  });

  it("renders artifact cards", () => {
    const message = makeMessage({
      artifacts: [
        {
          type: "zettel",
          action: "created",
          id: 1,
          title: "New card",
          summary: "A test card",
          tags: [],
        },
      ],
    });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.getByTestId("artifact-card")).toBeInTheDocument();
  });

  it("renders gap chips", () => {
    const message = makeMessage({
      gaps: [{ concept: "epistemology", description: "Knowledge gap", confidence: 0.8 }],
    });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.getByText("gap: epistemology")).toBeInTheDocument();
  });

  it("renders orchestration plan via ChainOfThought steps", () => {
    // With the AI Elements migration, plan rows surface through StepParts
    // grouped into a ChainOfThought block. Plan must be populated on
    // parts[] — the legacy plan[] field alone no longer renders anything
    // in the new primitives-based pipeline.
    const parts: MessagePart[] = [
      {
        type: "step",
        label: "knowledge: Search Polymath's knowledge base",
        state: "active",
        taskId: "task-1",
      },
    ];
    const message = makeMessage({
      plan: [
        {
          id: "task-1",
          agent: "knowledge",
          objective: "Search Polymath's knowledge base",
          status: "running",
        },
      ],
      parts,
    });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.getByTestId("ai-chain-of-thought")).toBeInTheDocument();
    expect(screen.getByTestId("ai-chain-step")).toHaveTextContent(
      "knowledge: Search Polymath's knowledge base",
    );
  });

  it("renders plan tasks from legacy message via synthesis (no parts[])", () => {
    // Simulates a DB-loaded message that has plan[] populated but no parts[].
    // Without the synthesizer extension, ChainOfThought would not render.
    const message = makeMessage({
      content: "Here is my answer.",
      plan: [
        {
          id: "task-1",
          agent: "knowledge",
          objective: "Search knowledge base",
          status: "done",
        },
        {
          id: "task-2",
          agent: "research",
          objective: "Deep research",
          status: "error",
        },
      ],
      parts: [],
    });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.getByTestId("ai-chain-of-thought")).toBeInTheDocument();
    const steps = screen.getAllByTestId("ai-chain-step");
    expect(steps).toHaveLength(2);
    expect(steps[0]).toHaveTextContent("knowledge: Search knowledge base");
    expect(steps[0]).toHaveAttribute("data-status", "complete");
    expect(steps[1]).toHaveTextContent("research: Deep research");
  });

  it("step with state=error renders with error indicator (icon + destructive class)", () => {
    const parts: MessagePart[] = [
      {
        type: "step",
        label: "research: Deep research",
        state: "error",
        description: "network timeout",
        taskId: "task-err",
      },
    ];
    const message = makeMessage({ content: "Partial answer.", parts });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    const step = screen.getByTestId("ai-chain-step");
    // Icon is rendered only when the error step passes one in.
    expect(screen.getByTestId("ai-chain-step-icon")).toBeInTheDocument();
    expect(step).toHaveAttribute("data-classname", "text-destructive");
    // Description is prefixed with "Error: " so the visual differs from
    // a successful step even when status is "complete".
    expect(step).toHaveAttribute("data-description", "Error: network timeout");
  });

  it("tool part in output-error state renders expanded (data-open=true)", () => {
    const parts: MessagePart[] = [
      {
        type: "tool-search_kb",
        toolCallId: "call-err",
        state: "output-error",
        input: { q: "monads" },
        errorText: "boom",
      },
    ];
    const message = makeMessage({ content: "Tool failed.", parts });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    const tool = screen.getByTestId("ai-tool");
    expect(tool).toHaveAttribute("data-open", "true");
  });

  it("tool part in input-available state does not render expanded by default", () => {
    const parts: MessagePart[] = [
      {
        type: "tool-search_kb",
        toolCallId: "call-ok",
        state: "input-available",
        input: { q: "monads" },
      },
    ];
    const message = makeMessage({ content: "Tool running.", parts });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    const tool = screen.getByTestId("ai-tool");
    expect(tool).toHaveAttribute("data-open", "false");
  });

  it("reasoning part exposes duration via mock prop", () => {
    const parts: MessagePart[] = [
      {
        type: "reasoning",
        text: "thinking",
        state: "done",
        startedAt: 1000,
        finishedAt: 4000, // 3s
      },
    ];
    const message = makeMessage({ reasoning: "thinking", parts });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    const reasoning = screen.getByTestId("ai-reasoning");
    expect(reasoning).toHaveAttribute("data-duration", "3");
    expect(reasoning).toHaveAttribute("data-streaming", "false");
  });

  it("renders approval-required section", () => {
    const message = makeMessage({
      pendingApprovals: [
        {
          id: "approval-1",
          action: "create_zettel",
          reason: "The synthesis should be saved as a new card",
          preview: {},
        },
      ],
    });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.getByText("Approval Needed")).toBeInTheDocument();
    expect(screen.getByText(/create_zettel/)).toBeInTheDocument();
  });

  it("shows a copy action for assistant messages in expanded chat", () => {
    const message = makeMessage({ content: "This is copied text." });

    render(<MessageBubble message={message} mode="expanded" onArtifactClick={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Copy response" })).toBeInTheDocument();
    expect(screen.getByText("Copy")).toBeInTheDocument();
  });

  it("shows a zettel action for assistant messages in expanded chat", () => {
    const message = makeMessage({ content: "This is copied text." });

    render(<MessageBubble message={message} mode="expanded" onArtifactClick={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Create zettel from response" })).toBeInTheDocument();
  });

  it("shows a note action for assistant messages in expanded chat", () => {
    const message = makeMessage({ content: "This is copied text." });

    render(<MessageBubble message={message} mode="expanded" onArtifactClick={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Save as note" })).toBeInTheDocument();
    expect(screen.getByText("Note")).toBeInTheDocument();
  });

  it("copies the assistant message text when copy is clicked", async () => {
    const user = userEvent.setup();
    const message = makeMessage({ content: "This is copied text." });

    render(<MessageBubble message={message} mode="expanded" onArtifactClick={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Copy response" }));

    expect(copyTextToClipboard).toHaveBeenCalledWith("This is copied text.");
    await waitFor(() => {
      expect(screen.getByText("Copied")).toBeInTheDocument();
    });
  });

  it("saves a zettel in sidebar mode and opens full view once saved", async () => {
    const user = userEvent.setup();
    const onViewZettel = vi.fn();
    const message = makeMessage({ content: "This is copied text." });

    vi.mocked(apiFetch).mockResolvedValue({ id: 321 });

    render(
      <MessageBubble
        message={message}
        mode="sidebar"
        onArtifactClick={vi.fn()}
        onViewZettel={onViewZettel}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Save as zettel" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "View zettel" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "View zettel" }));

    expect(onViewZettel).toHaveBeenCalledWith(321);
  });

  it("creates a zettel in expanded mode and opens it once saved", async () => {
    const user = userEvent.setup();
    const onViewZettel = vi.fn();
    const message = makeMessage({
      content: "## Systems thinking\n\nFeedback loops shape behavior over time.",
    });

    vi.mocked(apiFetch).mockResolvedValue({ id: 654 });

    render(
      <MessageBubble
        message={message}
        mode="expanded"
        onArtifactClick={vi.fn()}
        onViewZettel={onViewZettel}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Create zettel from response" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "View zettel" })).toBeInTheDocument();
    });

    expect(vi.mocked(apiFetch)).toHaveBeenCalledWith(
      "/api/zettels/cards",
      expect.objectContaining({
        method: "POST",
      }),
    );

    const [, requestInit] = vi.mocked(apiFetch).mock.calls[0] ?? [];
    expect(JSON.parse(String(requestInit?.body))).toMatchObject({
      title: "Systems thinking Feedback loops shape behavior over time.",
      content: "## Systems thinking\n\nFeedback loops shape behavior over time.",
      tags: [],
      topic: "",
    });

    await user.click(screen.getByRole("button", { name: "View zettel" }));

    expect(onViewZettel).toHaveBeenCalledWith(654);
  });

  it("saves a note from an assistant response and opens it once saved", async () => {
    const user = userEvent.setup();
    const onViewNote = vi.fn();
    const message = makeMessage({
      content: "## Meeting follow-up\n\nShip the reviewed implementation notes.",
    });

    vi.mocked(apiFetch).mockResolvedValue({ id: "note-123" });

    render(
      <MessageBubble
        message={message}
        mode="sidebar"
        onArtifactClick={vi.fn()}
        onViewNote={onViewNote}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Save as note" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "View note" })).toBeInTheDocument();
    });

    expect(vi.mocked(apiFetch)).toHaveBeenCalledWith(
      "/api/v1/notes",
      expect.objectContaining({
        method: "POST",
      }),
    );

    const [, requestInit] = vi.mocked(apiFetch).mock.calls[0] ?? [];
    expect(JSON.parse(String(requestInit?.body))).toMatchObject({
      title: "Meeting follow-up Ship the reviewed implementation notes.",
      content_markdown: "## Meeting follow-up\n\nShip the reviewed implementation notes.",
      content_json: null,
    });

    await user.click(screen.getByRole("button", { name: "View note" }));

    expect(onViewNote).toHaveBeenCalledWith("note-123");
  });

  it("lets users add review comments to an assistant response", async () => {
    const user = userEvent.setup();
    const onAddResponseComment = vi.fn();
    const message = makeMessage({ content: "Draft answer that needs review." });

    render(
      <MessageBubble
        message={message}
        mode="sidebar"
        onArtifactClick={vi.fn()}
        onAddResponseComment={onAddResponseComment}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Comment on block" }));
    await user.type(
      screen.getByPlaceholderText("Write a comment on this response..."),
      "Clarify the concrete next step.",
    );
    await user.click(screen.getByRole("button", { name: "Add" }));

    expect(onAddResponseComment).toHaveBeenCalledWith(
      "test-1",
      "Clarify the concrete next step.",
      expect.objectContaining({
        blockId: expect.stringMatching(/^block-0-/),
        blockPreview: "Draft answer that needs review.",
      }),
    );
  });

  it("exposes comment controls on each markdown block", () => {
    const message = makeMessage({
      content: "# Heading\n\nFirst paragraph.\n\n- One\n- Two",
    });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.getAllByRole("button", { name: "Comment on block" })).toHaveLength(3);
  });

  it("exposes zettelize controls on each markdown block", () => {
    const message = makeMessage({
      content: "# Heading\n\nFirst paragraph.\n\n- One\n- Two",
    });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.getAllByRole("button", { name: "Save block as zettel" })).toHaveLength(3);
  });

  it("zettelizes only the selected markdown block", async () => {
    const user = userEvent.setup();
    const onViewZettel = vi.fn();
    const message = makeMessage({
      content: "# Heading\n\nFirst paragraph.\n\nSecond paragraph.",
    });

    vi.mocked(apiFetch).mockResolvedValue({ id: 777 });

    render(
      <MessageBubble
        message={message}
        mode="sidebar"
        onArtifactClick={vi.fn()}
        onViewZettel={onViewZettel}
      />,
    );

    await user.click(screen.getAllByRole("button", { name: "Save block as zettel" })[1]);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "View block zettel" })).toBeInTheDocument();
    });

    expect(vi.mocked(apiFetch)).toHaveBeenCalledWith(
      "/api/zettels/cards",
      expect.objectContaining({
        method: "POST",
      }),
    );

    const [, requestInit] = vi.mocked(apiFetch).mock.calls[0] ?? [];
    expect(JSON.parse(String(requestInit?.body))).toMatchObject({
      title: "First paragraph.",
      content: "First paragraph.",
      tags: [],
      topic: "",
    });

    await user.click(screen.getByRole("button", { name: "View block zettel" }));

    expect(onViewZettel).toHaveBeenCalledWith(777);
  });

  it("tags commented responses and can ask Polymath to reply to the comments", async () => {
    const user = userEvent.setup();
    const onReplyToResponseComments = vi.fn();
    const message = makeMessage({ content: "Reviewed answer." });

    render(
      <MessageBubble
        message={message}
        mode="sidebar"
        responseComments={[
          {
            id: "comment-1",
            body: "This needs a stronger action list.",
            blockId: "block-0-review",
            blockPreview: "Reviewed answer.",
            createdAt: Date.now(),
          },
        ]}
        onArtifactClick={vi.fn()}
        onReplyToResponseComments={onReplyToResponseComments}
      />,
    );

    expect(screen.getByText("Commented · 1")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Reply to comments" }));

    expect(onReplyToResponseComments).toHaveBeenCalledWith(message);
  });

  describe("mode differences", () => {
    it("sidebar mode uses compact user bubble (max-w-[85%])", () => {
      const message = makeMessage({ role: "user", content: "Test" });
      const { container } = render(
        <MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />,
      );

      const bubble = container.querySelector("[class*='max-w-']");

      expect(bubble?.className).toContain("max-w-[85%]");
    });

    it("expanded mode uses spacious user bubble (max-w-[80%] rounded-2xl)", () => {
      const message = makeMessage({ role: "user", content: "Test" });
      const { container } = render(
        <MessageBubble message={message} mode="expanded" onArtifactClick={vi.fn()} />,
      );

      const bubble = container.querySelector("[class*='max-w-']");

      expect(bubble?.className).toContain("max-w-[80%]");
      expect(bubble?.className).toContain("rounded-2xl");
    });

    it("expanded mode wraps content with InsightToCard", () => {
      const message = makeMessage({ content: "Some insight" });

      render(<MessageBubble message={message} mode="expanded" onArtifactClick={vi.fn()} />);

      expect(screen.getByTestId("insight-to-card")).toBeInTheDocument();
    });

    it("sidebar mode does not wrap content with InsightToCard", () => {
      const message = makeMessage({ content: "Some insight" });

      render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

      expect(screen.queryByTestId("insight-to-card")).not.toBeInTheDocument();
    });

    it("expanded mode shows feedback buttons", () => {
      const message = makeMessage({ content: "A valid response" });
      render(<MessageBubble message={message} mode="expanded" onArtifactClick={vi.fn()} />);

      expect(screen.getByRole("button", { name: "Copy response" })).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Create zettel from response" }),
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Like response" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Dislike response" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Regenerate response" })).toBeInTheDocument();
    });
  });
});
