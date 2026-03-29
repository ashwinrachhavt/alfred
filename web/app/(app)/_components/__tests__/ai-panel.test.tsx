import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// jsdom doesn't implement scrollIntoView
Element.prototype.scrollIntoView = vi.fn();

// ---------------------------------------------------------------------------
// Mocks — must be before component import
// ---------------------------------------------------------------------------

const mockToggleAiPanel = vi.fn();

vi.mock("@/lib/stores/shell-store", () => ({
  useShellStore: vi.fn(() => ({
    aiPanelOpen: false,
    toggleAiPanel: mockToggleAiPanel,
  })),
}));

const defaultAgentState = {
  messages: [],
  threads: [],
  activeThreadId: null,
  isStreaming: false,
  activeLens: null,
  activeModel: "gpt-5.4",
  activeToolCalls: [],
  noteContext: null,
  sendMessage: vi.fn(),
  cancelStream: vi.fn(),
  setLens: vi.fn(),
  setModel: vi.fn(),
  loadThreads: vi.fn(),
  createThread: vi.fn(),
  clearMessages: vi.fn(),
};

vi.mock("@/lib/stores/agent-store", () => ({
  useAgentStore: Object.assign(vi.fn(() => defaultAgentState), {
    getState: vi.fn(() => defaultAgentState),
  }),
  PHILOSOPHICAL_LENSES: [
    { id: "socratic", label: "Socratic" },
    { id: "stoic", label: "Stoic" },
  ],
}));

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/notes"),
}));

vi.mock("@/lib/api/client", () => ({
  apiFetch: vi.fn(),
}));

vi.mock("@/components/agent/artifact-card", () => ({
  ArtifactCardComponent: () => <div data-testid="artifact-card" />,
}));

vi.mock("@/components/agent/related-cards", () => ({
  RelatedCards: () => <div data-testid="related-cards" />,
}));

vi.mock("@/components/agent/editor-drawer", () => ({
  EditorDrawer: () => <div data-testid="editor-drawer" />,
}));

vi.mock("@/components/agent/markdown-message", () => ({
  MarkdownMessage: ({ content }: { content: string }) => <div>{content}</div>,
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(" "),
}));

// Import AFTER all mocks
import { useShellStore } from "@/lib/stores/shell-store";
import { AiPanel } from "../ai-panel";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AiPanel", () => {
  it("renders nothing when aiPanelOpen is false", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: false,
      toggleAiPanel: mockToggleAiPanel,
    } as ReturnType<typeof useShellStore>);

    const { container } = render(<AiPanel />);
    expect(container.innerHTML).toBe("");
  });

  it("renders the panel with Alfred AI header when open", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: true,
      toggleAiPanel: mockToggleAiPanel,
    } as ReturnType<typeof useShellStore>);

    render(<AiPanel />);

    expect(screen.getByText("Alfred AI")).toBeInTheDocument();
    expect(screen.getByRole("complementary")).toBeInTheDocument();
  });

  it("shows page-contextual empty state suggestions for /notes", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: true,
      toggleAiPanel: mockToggleAiPanel,
    } as ReturnType<typeof useShellStore>);

    render(<AiPanel />);

    // On /notes with no noteContext, shows "notes-empty" suggestions
    expect(screen.getByText("What do I know about...")).toBeInTheDocument();
    expect(screen.getByText("Find connections between...")).toBeInTheDocument();
  });

  it("has an input textarea that is present", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: true,
      toggleAiPanel: mockToggleAiPanel,
    } as ReturnType<typeof useShellStore>);

    render(<AiPanel />);

    const textarea = screen.getByPlaceholderText("Ask about your knowledge...");
    expect(textarea).toBeInTheDocument();
    expect(textarea.tagName).toBe("TEXTAREA");
  });

  it("has a send button that is disabled when input is empty", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: true,
      toggleAiPanel: mockToggleAiPanel,
    } as ReturnType<typeof useShellStore>);

    render(<AiPanel />);

    const sendButton = screen.getByRole("button", { name: "Send message" });
    expect(sendButton).toBeDisabled();
  });
});
