import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

// jsdom doesn't implement scrollIntoView
Element.prototype.scrollIntoView = vi.fn();

// ---------------------------------------------------------------------------
// Mocks — must be before component import
// ---------------------------------------------------------------------------

const mockToggleAiPanel = vi.fn();
const mockToggleChatExpanded = vi.fn();
const mockSetChatMode = vi.fn();
const mockOpenZettelViewer = vi.fn();

vi.mock("@/lib/stores/shell-store", () => ({
  useShellStore: Object.assign(
    vi.fn(() => ({
      aiPanelOpen: true,
      chatMode: "sidebar" as const,
      toggleAiPanel: mockToggleAiPanel,
      toggleChatExpanded: mockToggleChatExpanded,
    })),
    {
      getState: vi.fn(() => ({
        setChatMode: mockSetChatMode,
        openZettelViewer: mockOpenZettelViewer,
      })),
    },
  ),
}));

const defaultAgentState = {
  messagesById: {},
  messageOrder: [],
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
  useAgentStore: Object.assign(
    vi.fn(() => defaultAgentState),
    {
      getState: vi.fn(() => defaultAgentState),
    },
  ),
  useToolCallStore: vi.fn(() => ({ activeToolCalls: [] })),
  selectOrderedMessages: vi.fn(() => []),
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

vi.mock("@/components/agent/insight-to-card", () => ({
  InsightToCard: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="insight-to-card">{children}</div>
  ),
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(" "),
}));

// Import AFTER all mocks
import { useShellStore } from "@/lib/stores/shell-store";
import { UnifiedChat } from "../unified-chat";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  mockSetChatMode.mockReset();
  mockOpenZettelViewer.mockReset();
});

describe("UnifiedChat — sidebar mode", () => {
  it("renders nothing when aiPanelOpen is false", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: false,
      chatMode: "sidebar",
      toggleAiPanel: mockToggleAiPanel,
      toggleChatExpanded: mockToggleChatExpanded,
    } as unknown as ReturnType<typeof useShellStore>);

    const { container } = render(<UnifiedChat mode="sidebar" />);
    expect(container.innerHTML).toBe("");
  });

  it("renders the panel with Alfred AI header when open", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: true,
      chatMode: "sidebar",
      toggleAiPanel: mockToggleAiPanel,
      toggleChatExpanded: mockToggleChatExpanded,
    } as unknown as ReturnType<typeof useShellStore>);

    render(<UnifiedChat mode="sidebar" />);

    expect(screen.getByText("Alfred AI")).toBeInTheDocument();
    expect(screen.getByRole("complementary")).toBeInTheDocument();
  });

  it("shows page-contextual empty state suggestions for /notes", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: true,
      chatMode: "sidebar",
      toggleAiPanel: mockToggleAiPanel,
      toggleChatExpanded: mockToggleChatExpanded,
    } as unknown as ReturnType<typeof useShellStore>);

    render(<UnifiedChat mode="sidebar" />);

    expect(screen.getByText("What do I know about...")).toBeInTheDocument();
    expect(screen.getByText("Find connections between...")).toBeInTheDocument();
  });

  it("has an input textarea that is present", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: true,
      chatMode: "sidebar",
      toggleAiPanel: mockToggleAiPanel,
      toggleChatExpanded: mockToggleChatExpanded,
    } as unknown as ReturnType<typeof useShellStore>);

    render(<UnifiedChat mode="sidebar" />);

    const textarea = screen.getByPlaceholderText("Ask about your knowledge...");
    expect(textarea).toBeInTheDocument();
    expect(textarea.tagName).toBe("TEXTAREA");
  });

  it("has a send button that is disabled when input is empty", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: true,
      chatMode: "sidebar",
      toggleAiPanel: mockToggleAiPanel,
      toggleChatExpanded: mockToggleChatExpanded,
    } as unknown as ReturnType<typeof useShellStore>);

    render(<UnifiedChat mode="sidebar" />);

    const sendButton = screen.getByRole("button", { name: "Send message" });
    expect(sendButton).toBeDisabled();
  });

  it("has a close button that calls toggleAiPanel", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: true,
      chatMode: "sidebar",
      toggleAiPanel: mockToggleAiPanel,
      toggleChatExpanded: mockToggleChatExpanded,
    } as unknown as ReturnType<typeof useShellStore>);

    render(<UnifiedChat mode="sidebar" />);

    const closeButton = screen.getByRole("button", { name: "Close AI panel" });
    fireEvent.click(closeButton);
    expect(mockToggleAiPanel).toHaveBeenCalledTimes(1);
  });

  it("has an expand button that calls toggleChatExpanded", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: true,
      chatMode: "sidebar",
      toggleAiPanel: mockToggleAiPanel,
      toggleChatExpanded: mockToggleChatExpanded,
    } as unknown as ReturnType<typeof useShellStore>);

    render(<UnifiedChat mode="sidebar" />);

    const expandButton = screen.getByRole("button", { name: "Expand chat" });
    fireEvent.click(expandButton);
    expect(mockToggleChatExpanded).toHaveBeenCalledTimes(1);
  });

  it("uses w-[380px] width in sidebar mode", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: true,
      chatMode: "sidebar",
      toggleAiPanel: mockToggleAiPanel,
      toggleChatExpanded: mockToggleChatExpanded,
    } as unknown as ReturnType<typeof useShellStore>);

    render(<UnifiedChat mode="sidebar" />);

    const panel = screen.getByRole("complementary");
    expect(panel.className).toContain("w-[380px]");
  });
});

describe("UnifiedChat — expanded mode", () => {
  it("always renders in expanded mode (ignores aiPanelOpen)", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: false,
      chatMode: "expanded",
      toggleAiPanel: mockToggleAiPanel,
      toggleChatExpanded: mockToggleChatExpanded,
    } as unknown as ReturnType<typeof useShellStore>);

    render(<UnifiedChat mode="expanded" />);

    expect(screen.getByText("Alfred AI")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("has a collapse button", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: true,
      chatMode: "expanded",
      toggleAiPanel: mockToggleAiPanel,
      toggleChatExpanded: mockToggleChatExpanded,
    } as unknown as ReturnType<typeof useShellStore>);

    render(<UnifiedChat mode="expanded" />);

    const collapseButton = screen.getByRole("button", {
      name: "Collapse to sidebar",
    });
    fireEvent.click(collapseButton);
    expect(mockToggleChatExpanded).toHaveBeenCalledTimes(1);
  });

  it("shows spacious empty state with description", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: true,
      chatMode: "expanded",
      toggleAiPanel: mockToggleAiPanel,
      toggleChatExpanded: mockToggleChatExpanded,
    } as unknown as ReturnType<typeof useShellStore>);

    render(<UnifiedChat mode="expanded" />);

    expect(screen.getByText("What would you like to explore?")).toBeInTheDocument();
    expect(screen.getByText(/Alfred will search your knowledge base/)).toBeInTheDocument();
  });

  it("uses max-w-3xl centered layout for messages", () => {
    vi.mocked(useShellStore).mockReturnValue({
      aiPanelOpen: true,
      chatMode: "expanded",
      toggleAiPanel: mockToggleAiPanel,
      toggleChatExpanded: mockToggleChatExpanded,
    } as unknown as ReturnType<typeof useShellStore>);

    render(<UnifiedChat mode="expanded" />);

    const messagesArea = screen.getByRole("log");
    const innerDiv = messagesArea.firstChild as HTMLElement;
    expect(innerDiv.className).toContain("max-w-3xl");
    expect(innerDiv.className).toContain("mx-auto");
  });
});
