import { useEffect } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useStickToBottom } from "../use-stick-to-bottom";

const scrollIntoViewMock = vi.fn();

function HookHarness({ itemCount }: { itemCount: number }) {
  const { containerRef, endRef, maybeScrollToBottom, scrollToBottom } = useStickToBottom();

  useEffect(() => {
    maybeScrollToBottom("auto");
  }, [itemCount, maybeScrollToBottom]);

  return (
    <>
      <div ref={containerRef} data-testid="scroll-container">
        {Array.from({ length: itemCount }, (_, index) => (
          <div key={index}>Row {index}</div>
        ))}
        <div ref={endRef} />
      </div>
      <button type="button" onClick={() => scrollToBottom("smooth")}>
        Jump
      </button>
    </>
  );
}

function setScrollMetrics(
  element: HTMLElement,
  metrics: { clientHeight: number; scrollHeight: number; scrollTop: number },
) {
  Object.defineProperty(element, "clientHeight", {
    configurable: true,
    value: metrics.clientHeight,
  });
  Object.defineProperty(element, "scrollHeight", {
    configurable: true,
    value: metrics.scrollHeight,
  });
  Object.defineProperty(element, "scrollTop", {
    configurable: true,
    writable: true,
    value: metrics.scrollTop,
  });
}

beforeEach(() => {
  scrollIntoViewMock.mockReset();
  Element.prototype.scrollIntoView = scrollIntoViewMock;
});

describe("useStickToBottom", () => {
  it("keeps following streamed content while the user stays near the bottom", () => {
    const { rerender } = render(<HookHarness itemCount={2} />);
    const container = screen.getByTestId("scroll-container");

    setScrollMetrics(container, {
      clientHeight: 300,
      scrollHeight: 1000,
      scrollTop: 700,
    });
    fireEvent.scroll(container);

    scrollIntoViewMock.mockClear();
    rerender(<HookHarness itemCount={3} />);

    expect(scrollIntoViewMock).toHaveBeenCalledTimes(1);
    expect(scrollIntoViewMock).toHaveBeenCalledWith({
      behavior: "auto",
      block: "end",
    });
  });

  it("stops auto-scrolling once the user scrolls away from the bottom", () => {
    const { rerender } = render(<HookHarness itemCount={2} />);
    const container = screen.getByTestId("scroll-container");

    setScrollMetrics(container, {
      clientHeight: 300,
      scrollHeight: 1000,
      scrollTop: 200,
    });
    fireEvent.scroll(container);

    scrollIntoViewMock.mockClear();
    rerender(<HookHarness itemCount={3} />);

    expect(scrollIntoViewMock).not.toHaveBeenCalled();
  });

  it("can resume bottom following after an explicit jump", () => {
    const { rerender } = render(<HookHarness itemCount={2} />);
    const container = screen.getByTestId("scroll-container");

    setScrollMetrics(container, {
      clientHeight: 300,
      scrollHeight: 1000,
      scrollTop: 200,
    });
    fireEvent.scroll(container);

    fireEvent.click(screen.getByRole("button", { name: "Jump" }));
    scrollIntoViewMock.mockClear();

    rerender(<HookHarness itemCount={3} />);

    expect(scrollIntoViewMock).toHaveBeenCalledTimes(1);
    expect(scrollIntoViewMock).toHaveBeenCalledWith({
      behavior: "auto",
      block: "end",
    });
  });
});
