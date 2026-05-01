"use client";

import { useCallback, useSyncExternalStore, type Dispatch, type SetStateAction } from "react";

import { safeGetItem, safeSetItem } from "@/lib/storage";

const LOCAL_STORAGE_VALUE_EVENT = "alfred:local-storage-value-change";
const memoryValues = new Map<string, string>();

function getRawValue(key: string): string | null {
  if (typeof window === "undefined") return memoryValues.get(key) ?? null;
  return safeGetItem(key) ?? memoryValues.get(key) ?? null;
}

function setRawValue(key: string, value: string): void {
  memoryValues.set(key, value);
  safeSetItem(key, value);
  window.dispatchEvent(new CustomEvent(LOCAL_STORAGE_VALUE_EVENT, { detail: { key } }));
}

function subscribeToKey(key: string, onStoreChange: () => void): () => void {
  const handleStorage = (event: StorageEvent) => {
    if (event.key === key) onStoreChange();
  };
  const handleLocalChange = (event: Event) => {
    if (!(event instanceof CustomEvent)) return;
    if ((event.detail as { key?: string } | null)?.key === key) onStoreChange();
  };

  window.addEventListener("storage", handleStorage);
  window.addEventListener(LOCAL_STORAGE_VALUE_EVENT, handleLocalChange);
  return () => {
    window.removeEventListener("storage", handleStorage);
    window.removeEventListener(LOCAL_STORAGE_VALUE_EVENT, handleLocalChange);
  };
}

function readNumber(key: string, fallback: number): number {
  const raw = getRawValue(key);
  const parsed = raw ? Number(raw) : Number.NaN;
  return Number.isFinite(parsed) ? parsed : fallback;
}

function readBoolean(key: string, fallback: boolean): boolean {
  const raw = getRawValue(key);
  if (raw === "true") return true;
  if (raw === "false") return false;
  return fallback;
}

export function useLocalStorageNumber(
  key: string,
  fallback: number,
): readonly [number, Dispatch<SetStateAction<number>>] {
  const subscribe = useCallback(
    (onStoreChange: () => void) => subscribeToKey(key, onStoreChange),
    [key],
  );
  const getSnapshot = useCallback(() => readNumber(key, fallback), [fallback, key]);
  const getServerSnapshot = useCallback(() => fallback, [fallback]);
  const value = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const setValue = useCallback<Dispatch<SetStateAction<number>>>(
    (next) => {
      const resolved = typeof next === "function" ? next(readNumber(key, fallback)) : next;
      setRawValue(key, String(resolved));
    },
    [fallback, key],
  );

  return [value, setValue];
}

export function useLocalStorageString(
  key: string,
  fallback: string,
): readonly [string, Dispatch<SetStateAction<string>>] {
  const subscribe = useCallback(
    (onStoreChange: () => void) => subscribeToKey(key, onStoreChange),
    [key],
  );
  const getSnapshot = useCallback(() => getRawValue(key) ?? fallback, [fallback, key]);
  const getServerSnapshot = useCallback(() => fallback, [fallback]);
  const value = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const setValue = useCallback<Dispatch<SetStateAction<string>>>(
    (next) => {
      const resolved = typeof next === "function" ? next(getRawValue(key) ?? fallback) : next;
      setRawValue(key, resolved);
    },
    [fallback, key],
  );

  return [value, setValue];
}

export function useLocalStorageBoolean(
  key: string,
  fallback: boolean,
): readonly [boolean, Dispatch<SetStateAction<boolean>>] {
  const subscribe = useCallback(
    (onStoreChange: () => void) => subscribeToKey(key, onStoreChange),
    [key],
  );
  const getSnapshot = useCallback(() => readBoolean(key, fallback), [fallback, key]);
  const getServerSnapshot = useCallback(() => fallback, [fallback]);
  const value = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const setValue = useCallback<Dispatch<SetStateAction<boolean>>>(
    (next) => {
      const resolved = typeof next === "function" ? next(readBoolean(key, fallback)) : next;
      setRawValue(key, String(resolved));
    },
    [fallback, key],
  );

  return [value, setValue];
}
