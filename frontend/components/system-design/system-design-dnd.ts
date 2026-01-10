import type { ComponentDefinition } from "@/lib/api/types/system-design";

export const SYSTEM_DESIGN_COMPONENT_DND_MIME = "application/x-alfred-system-design-component";

export type SystemDesignComponentDragPayload = {
  id: string;
  name: string;
  category: string;
};

type ComponentDragSource = Pick<ComponentDefinition, "id" | "name" | "category">;

/**
 * Converts a component definition into a drag payload that can be serialized and
 * dropped onto the Excalidraw canvas.
 */
export function toSystemDesignComponentDragPayload(
  component: ComponentDragSource,
): SystemDesignComponentDragPayload {
  return {
    id: component.id,
    name: component.name,
    category: component.category,
  };
}

/**
 * Serializes a component drag payload for use with the HTML Drag and Drop API.
 */
export function encodeSystemDesignComponentDragPayload(payload: SystemDesignComponentDragPayload) {
  return JSON.stringify(payload);
}

/**
 * Attempts to parse a component drag payload from an HTML Drag and Drop data string.
 */
export function decodeSystemDesignComponentDragPayload(
  raw: string | null,
): SystemDesignComponentDragPayload | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return null;

    const record = parsed as Record<string, unknown>;
    if (typeof record.id !== "string") return null;
    if (typeof record.name !== "string") return null;
    if (typeof record.category !== "string") return null;

    return {
      id: record.id,
      name: record.name,
      category: record.category,
    };
  } catch {
    return null;
  }
}

