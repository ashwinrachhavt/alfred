import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/components/agent/artifact-card", () => ({
  ArtifactCardComponent: ({ artifact }: { artifact: { title: string } }) => (
    <div data-testid="artifact-card">{artifact.title}</div>
  ),
}));

vi.mock("@/components/agent/related-cards", () => ({
  RelatedCards: () => <div data-testid="related-cards" />,
}));

vi.mock("@/components/agent/insight-to-card", () => ({
  InsightToCard: ({ children }: { children: React.ReactNode }) => (
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

vi.mock("@/lib/utils", () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(" "),
}));

import { MessageBubble } from "../message-bubble";
import type { AgentMessage } from "@/lib/stores/agent-store";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("MessageBubble", () => {
  it("renders user message as right-aligned bubble", () => {
    const msg = makeMessage({ role: "user", content: "My question" });
    render(
      <MessageBubble
        message={msg}
        mode="sidebar"
        onArtifactClick={vi.fn()}
      />,
    );
    expect(screen.getByText("My question")).toBeInTheDocument();
  });

  it("renders assistant message with markdown content", () => {
    const msg = makeMessage({ content: "Test response" });
    render(
      <MessageBubble
        message={msg}
        mode="sidebar"
        onArtifactClick={vi.fn()}
      />,
    );
    expect(screen.getByTestId("markdown-message")).toBeInTheDocument();
    expect(screen.getByText("Test response")).toBeInTheDocument();
  });

  it("shows reasoning trace when reasoning exists", () => {
    const msg = makeMessage({ reasoning: "Let me think about this..." });
    render(
      <MessageBubble
        message={msg}
        mode="sidebar"
        onArtifactClick={vi.fn()}
      />,
    );
    // Reasoning is collapsed by default — shows "Thinking" label
    expect(screen.getByText("Thinking")).toBeInTheDocument();
  });

  it("expands reasoning trace on click", () => {
    const msg = makeMessage({ reasoning: "Deep thoughts here" });
    render(
      <MessageBubble
        message={msg}
        mode="sidebar"
        onArtifactClick={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("Thinking"));
    expect(screen.getByText("Deep thoughts here")).toBeInTheDocument();
  });

  it("does not show reasoning section when reasoning is absent", () => {
    const msg = makeMessage({ reasoning: undefined });
    render(
      <MessageBubble
        message={msg}
        mode="sidebar"
        onArtifactClick={vi.fn()}
      />,
    );
    expect(screen.queryByText("Thinking")).not.toBeInTheDocument();
  });

  it("shows tool calls with status indicators", () => {
    const msg = makeMessage({
      toolCalls: [
        { tool: "search_kb", args: {}, status: "pending" },
        { tool: "create_zettel", args: {}, status: "done", call_id: "c1" },
      ],
    });
    render(
      <MessageBubble
        message={msg}
        mode="sidebar"
        onArtifactClick={vi.fn()}
      />,
    );
    expect(screen.getByText("search kb")).toBeInTheDocument();
    expect(screen.getByText("create zettel")).toBeInTheDocument();
  });

  it("renders artifact cards", () => {
    const msg = makeMessage({
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
    render(
      <MessageBubble
        message={msg}
        mode="sidebar"
        onArtifactClick={vi.fn()}
      />,
    );
    expect(screen.getByTestId("artifact-card")).toBeInTheDocument();
  });

  it("renders gap chips", () => {
    const msg = makeMessage({
      gaps: [
        { concept: "epistemology", description: "Knowledge gap", confidence: 0.8 },
      ],
    });
    render(
      <MessageBubble
        message={msg}
        mode="sidebar"
        onArtifactClick={vi.fn()}
      />,
    );
    expect(screen.getByText("gap: epistemology")).toBeInTheDocument();
  });

  it("renders orchestration plan rows", () => {
    const msg = makeMessage({
      plan: [
        {
          id: "task-1",
          agent: "knowledge",
          objective: "Search Alfred's knowledge base",
          status: "running",
        },
      ],
    });
    render(
      <MessageBubble
        message={msg}
        mode="sidebar"
        onArtifactClick={vi.fn()}
      />,
    );
    expect(screen.getByText("Plan")).toBeInTheDocument();
    expect(screen.getByText(/knowledge: Search Alfred's knowledge base/)).toBeInTheDocument();
  });

  it("renders approval-required section", () => {
    const msg = makeMessage({
      pendingApprovals: [
        {
          id: "approval-1",
          action: "create_zettel",
          reason: "The synthesis should be saved as a new card",
          preview: {},
        },
      ],
    });
    render(
      <MessageBubble
        message={msg}
        mode="sidebar"
        onArtifactClick={vi.fn()}
      />,
    );
    expect(screen.getByText("Approval Needed")).toBeInTheDocument();
    expect(screen.getByText(/create_zettel/)).toBeInTheDocument();
  });

  describe("mode differences", () => {
    it("sidebar mode uses compact user bubble (max-w-[85%])", () => {
      const msg = makeMessage({ role: "user", content: "Test" });
      const { container } = render(
        <MessageBubble
          message={msg}
          mode="sidebar"
          onArtifactClick={vi.fn()}
        />,
      );
      const bubble = container.querySelector("[class*='max-w-']");
      expect(bubble?.className).toContain("max-w-[85%]");
    });

    it("expanded mode uses spacious user bubble (max-w-[80%] rounded-2xl)", () => {
      const msg = makeMessage({ role: "user", content: "Test" });
      const { container } = render(
        <MessageBubble
          message={msg}
          mode="expanded"
          onArtifactClick={vi.fn()}
        />,
      );
      const bubble = container.querySelector("[class*='max-w-']");
      expect(bubble?.className).toContain("max-w-[80%]");
      expect(bubble?.className).toContain("rounded-2xl");
    });

    it("expanded mode wraps content with InsightToCard", () => {
      const msg = makeMessage({ content: "Some insight" });
      render(
        <MessageBubble
          message={msg}
          mode="expanded"
          onArtifactClick={vi.fn()}
        />,
      );
      expect(screen.getByTestId("insight-to-card")).toBeInTheDocument();
    });

    it("sidebar mode does NOT wrap content with InsightToCard", () => {
      const msg = makeMessage({ content: "Some insight" });
      render(
        <MessageBubble
          message={msg}
          mode="sidebar"
          onArtifactClick={vi.fn()}
        />,
      );
      expect(screen.queryByTestId("insight-to-card")).not.toBeInTheDocument();
    });

    it("expanded mode shows feedback buttons (thumbs up/down, regenerate)", () => {
      const msg = makeMessage({ content: "A valid response" });
      const { container } = render(
        <MessageBubble
          message={msg}
          mode="expanded"
          onArtifactClick={vi.fn()}
        />,
      );
      // Feedback buttons are always rendered in expanded mode (not hidden on hover)
      // We check for the SVG icons by their parent buttons
      const buttons = container.querySelectorAll("button");
      // Should have at least 3 feedback buttons (thumbs up, down, regenerate)
      expect(buttons.length).toBeGreaterThanOrEqual(3);
    });
  });
});
