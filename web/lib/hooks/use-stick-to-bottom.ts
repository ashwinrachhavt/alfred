"use client";

import { useCallback, useEffect, useRef } from "react";

type UseStickToBottomOptions = {
  threshold?: number;
};

export function useStickToBottom(options: UseStickToBottomOptions = {}) {
  const { threshold = 96 } = options;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const shouldStickRef = useRef(true);

  const syncBottomState = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    const nextIsAtBottom = distanceFromBottom <= threshold;

    shouldStickRef.current = nextIsAtBottom;
  }, [threshold]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    syncBottomState();

    const handleScroll = () => {
      syncBottomState();
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      container.removeEventListener("scroll", handleScroll);
    };
  }, [syncBottomState]);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    shouldStickRef.current = true;
    endRef.current?.scrollIntoView({ behavior, block: "end" });
  }, []);

  const maybeScrollToBottom = useCallback((behavior: ScrollBehavior = "auto") => {
    if (!shouldStickRef.current) return;
    endRef.current?.scrollIntoView({ behavior, block: "end" });
  }, []);

  return {
    containerRef,
    endRef,
    maybeScrollToBottom,
    scrollToBottom,
  };
}
