"use client";

import * as React from "react";

/**
 * Returns a timestamp that updates on an interval.
 *
 * This avoids calling non-idempotent time APIs during render, while still
 * letting UI surfaces show "due now" or "overdue" states that refresh over time.
 */
export function useNowMs(intervalMs = 30_000): number {
  const [nowMs, setNowMs] = React.useState(0);

  React.useEffect(() => {
    const update = () => setNowMs(Date.now());
    update();

    const interval = window.setInterval(update, intervalMs);
    return () => window.clearInterval(interval);
  }, [intervalMs]);

  return nowMs;
}
