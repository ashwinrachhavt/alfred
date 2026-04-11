import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentMessage } from "@/lib/stores/agent-store";
import { apiFetch } from "@/lib/api/client";

const { copyTextToClipboard } = vi.hoisted(() => ({
  copyTextToClipboard: vi.fn(),
}));

vi.mock("@/components/agent/artifact-card", () => ({
  ArtifactCardComponent: () => null,
}));

vi.mock("@/components/agent/related-cards", () => ({
  RelatedCards: () => null,
}));

vi.mock("@/components/agent/insight-to-card", () => ({
  InsightToCard: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/agent/markdown-message", () => ({
  MarkdownMessage: ({ content }: { content: string }) => <div>{content}</div>,
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

const assistantMessage: AgentMessage = {
  id: "msg-1",
  role: "assistant",
  content: "This is copied text.",
  artifacts: [],
  relatedCards: [],
  gaps: [],
  toolCalls: [],
  timestamp: Date.now(),
};

describe("MessageBubble", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    copyTextToClipboard.mockResolvedValue(undefined);
  });

  it("shows a copy action for assistant messages in expanded chat", () => {
    render(<MessageBubble message={assistantMessage} mode="expanded" onArtifactClick={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Copy response" })).toBeInTheDocument();
    expect(screen.getByText("Copy")).toBeInTheDocument();
  });

  it("copies the assistant message text when copy is clicked", async () => {
    const user = userEvent.setup();

    render(<MessageBubble message={assistantMessage} mode="expanded" onArtifactClick={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Copy response" }));

    expect(copyTextToClipboard).toHaveBeenCalledWith("This is copied text.");
    await waitFor(() => {
      expect(screen.getByText("Copied")).toBeInTheDocument();
    });
  });

  it("saves a zettel in sidebar mode and opens full view once saved", async () => {
    const user = userEvent.setup();
    const onViewZettel = vi.fn();

    vi.mocked(apiFetch).mockResolvedValue({ id: 321 });

    render(
      <MessageBubble
        message={assistantMessage}
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
});
