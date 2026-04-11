import { useSyncExternalStore } from "react";

function subscribe(): () => void {
  return () => {};
}

function getSnapshot(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

function getServerSnapshot(): string {
  return "UTC";
}

export function useBrowserTimeZone(): string {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
