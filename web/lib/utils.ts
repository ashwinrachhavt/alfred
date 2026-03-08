import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import { ApiError } from "@/lib/api/client";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Extract a human-readable message from an unknown caught value. */
export function formatErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

/** Narrow an unknown value to a plain object. */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Safely coerce an unknown value to string, returning null otherwise. */
export function coerceString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}
