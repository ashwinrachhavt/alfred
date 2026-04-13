import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useQueries } from "@tanstack/react-query";

import { useZettelCard } from "@/features/zettels/queries";

import { ZettelFullView } from "../zettel-full-view";

const { mockCloseZettelViewer, mockOpenZettelViewer } = vi.hoisted(() => ({
  mockCloseZettelViewer: vi.fn(),
  mockOpenZettelViewer: vi.fn(),
}));

vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-query")>(
    "@tanstack/react-query",
  );

  return {
    ...actual,
    useQueries: vi.fn(),
  };
});

vi.mock("@/features/zettels/queries", () => ({
  useZettelCard: vi.fn(),
}));

vi.mock("@/lib/stores/shell-store", () => ({
  useShellStore: (
    selector: (state: {
      closeZettelViewer: typeof mockCloseZettelViewer;
      openZettelViewer: typeof mockOpenZettelViewer;
    }) => unknown,
  ) =>
    selector({
      closeZettelViewer: mockCloseZettelViewer,
      openZettelViewer: mockOpenZettelViewer,
    }),
}));

vi.mock("../zettel-link-suggestions", () => ({
  ZettelLinkSuggestions: ({
    labelClassName,
  }: {
    labelClassName?: string;
  }) => (
    <section>
      <div className={labelClassName}>AI Suggestions</div>
      <p>Mock suggestions</p>
    </section>
  ),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    onClick,
  }: {
    children: React.ReactNode;
    href: string;
    onClick?: () => void;
  }) => (
    <a href={href} onClick={onClick}>
      {children}
    </a>
  ),
}));

describe("ZettelFullView", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(useQueries).mockReturnValue([]);
    vi.mocked(useZettelCard).mockReturnValue({
      data: {
        id: "123",
        title: "Trigger of World War II",
        content:
          "# Trigger of World War II\n\nThe immediate trigger for World War II in Europe was Nazi Germany's invasion of Poland.",
        summary:
          "World War II was directly triggered in Europe by Germany's invasion of Poland, which prompted Britain and France to declare war.",
        preview: "",
        tags: ["worldwar2", "poland", "germany"],
        connections: [],
        status: "active",
        bloomLevel: 6,
        bloomHistory: [],
        source: {
          title: "History notes",
          capturedAt: "2026-04-12T10:33:00Z",
        },
        lastReviewedAt: null,
        nextReviewAt: null,
        quizHistory: { attempts: 0, correct: 0 },
        quizQuestions: [],
        feynmanGaps: [],
        createdAt: "2026-04-12T10:33:00Z",
        updatedAt: "2026-04-12T10:34:00Z",
      },
      isLoading: false,
      isError: false,
    });
  });

  it("renders reading flow before bloom and AI suggestions", () => {
    render(<ZettelFullView zettelId={123} variant="dialog" />);

    const summary = screen.getByText("Summary");
    const content = screen.getByText("Content");
    const bloom = screen.getByText("Bloom Level");
    const suggestions = screen.getByText("AI Suggestions");

    expect(screen.getAllByText("Trigger of World War II")).toHaveLength(1);
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    expect(summary.compareDocumentPosition(content) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(content.compareDocumentPosition(bloom) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(bloom.compareDocumentPosition(suggestions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
