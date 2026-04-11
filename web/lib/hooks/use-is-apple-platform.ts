import { useSyncExternalStore } from "react";

function subscribe(): () => void {
  return () => {};
}

function getSnapshot(): boolean {
  return typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/i.test(navigator.platform);
}

function getServerSnapshot(): boolean {
  return false;
}

export function useIsApplePlatform(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
