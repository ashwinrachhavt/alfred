import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "@/lib/api/client";
import type { AgentMessage } from "@/lib/stores/agent-store";

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

vi.mock("@/components/agent/markdown-message", () => ({
  MarkdownMessage: ({ content }: { content: string }) => (
    <div data-testid="markdown-message">{content}</div>
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

    expect(screen.getByTestId("markdown-message")).toBeInTheDocument();
    expect(screen.getByText("Test response")).toBeInTheDocument();
  });

  it("shows reasoning trace when reasoning exists", () => {
    const message = makeMessage({ reasoning: "Let me think about this..." });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.getByText("Thinking")).toBeInTheDocument();
  });

  it("expands reasoning trace on click", () => {
    const message = makeMessage({ reasoning: "Deep thoughts here" });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    fireEvent.click(screen.getByText("Thinking"));

    expect(screen.getByText("Deep thoughts here")).toBeInTheDocument();
  });

  it("does not show reasoning section when reasoning is absent", () => {
    const message = makeMessage({ reasoning: undefined });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.queryByText("Thinking")).not.toBeInTheDocument();
  });

  it("shows tool calls with status indicators", () => {
    const message = makeMessage({
      toolCalls: [
        { tool: "search_kb", args: {}, status: "pending" },
        { tool: "create_zettel", args: {}, status: "done", call_id: "c1" },
      ],
    });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.getByText("search kb")).toBeInTheDocument();
    expect(screen.getByText("create zettel")).toBeInTheDocument();
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

  it("renders orchestration plan rows", () => {
    const message = makeMessage({
      plan: [
        {
          id: "task-1",
          agent: "knowledge",
          objective: "Search Alfred's knowledge base",
          status: "running",
        },
      ],
    });

    render(<MessageBubble message={message} mode="sidebar" onArtifactClick={vi.fn()} />);

    expect(screen.getByText("Plan")).toBeInTheDocument();
    expect(screen.getByText(/knowledge: Search Alfred's knowledge base/)).toBeInTheDocument();
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
      const { container } = render(
        <MessageBubble message={message} mode="expanded" onArtifactClick={vi.fn()} />,
      );

      const buttons = container.querySelectorAll("button");

      expect(buttons.length).toBeGreaterThanOrEqual(4);
    });
  });
});
