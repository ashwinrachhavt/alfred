import type { ExcalidrawData } from "@/lib/api/types/system-design";

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return Boolean(value) && typeof value === "object";
}

function getString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function sanitizeInline(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

function escapePlantUmlLabel(text: string): string {
  return sanitizeInline(text).replaceAll('"', '\\"');
}

function escapeMermaidLabel(text: string): string {
  return sanitizeInline(text).replaceAll("|", "/").replaceAll('"', "'");
}

function getElementId(element: unknown): string | null {
  if (!isRecord(element)) return null;
  return getString(element.id);
}

function getElementType(element: unknown): string | null {
  if (!isRecord(element)) return null;
  return getString(element.type);
}

function isDeleted(element: unknown): boolean {
  if (!isRecord(element)) return false;
  return Boolean(element.isDeleted);
}

function buildTextByContainerId(elements: unknown[]): Map<string, string> {
  const map = new Map<string, string>();
  for (const element of elements) {
    if (isDeleted(element)) continue;
    if (getElementType(element) !== "text") continue;
    if (!isRecord(element)) continue;

    const containerId = getString(element.containerId);
    const text = getString(element.text);
    if (!containerId || !text) continue;

    const normalized = sanitizeInline(text);
    if (normalized) map.set(containerId, normalized);
  }
  return map;
}

function getElementLabel(element: unknown, textByContainerId: Map<string, string>): string {
  if (!isRecord(element)) return "Untitled";

  const id = getString(element.id);
  if (id && textByContainerId.has(id)) return textByContainerId.get(id) ?? "Untitled";

  const label = element.label;
  if (isRecord(label)) {
    const labelText = getString(label.text);
    if (labelText) return sanitizeInline(labelText);
  }

  return "Untitled";
}

function getBindingElementId(binding: unknown): string | null {
  if (!isRecord(binding)) return null;
  return getString(binding.elementId);
}

type GraphNode = { id: string; label: string; type: string };
type GraphEdge = { from: string; to: string; label?: string };

function extractGraph(diagram: ExcalidrawData): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const elements = Array.isArray(diagram.elements) ? diagram.elements : [];
  const textByContainerId = buildTextByContainerId(elements);

  const nodes: GraphNode[] = [];
  const nodeIds = new Set<string>();
  for (const element of elements) {
    if (isDeleted(element)) continue;
    const type = getElementType(element);
    const id = getElementId(element);
    if (!type || !id) continue;
    if (type === "text" || type === "arrow" || type === "line") continue;
    nodeIds.add(id);
    nodes.push({ id, type, label: getElementLabel(element, textByContainerId) });
  }

  const edges: GraphEdge[] = [];
  for (const element of elements) {
    if (isDeleted(element)) continue;
    const type = getElementType(element);
    const id = getElementId(element);
    if (!type || !id) continue;
    if (type !== "arrow" && type !== "line") continue;
    if (!isRecord(element)) continue;

    const from = getBindingElementId(element.startBinding);
    const to = getBindingElementId(element.endBinding);
    if (!from || !to) continue;
    if (!nodeIds.has(from) || !nodeIds.has(to)) continue;

    const label = getElementLabel(element, textByContainerId);
    edges.push({ from, to, label: label !== "Untitled" ? label : undefined });
  }

  nodes.sort((a, b) => a.label.localeCompare(b.label));
  edges.sort((a, b) => a.from.localeCompare(b.from) || a.to.localeCompare(b.to));

  return { nodes, edges };
}

export function diagramToMermaid(diagram: ExcalidrawData): string {
  const { nodes, edges } = extractGraph(diagram);
  const ids = new Map(nodes.map((node, idx) => [node.id, `N${idx + 1}`]));

  const lines = ["flowchart LR"];

  for (const node of nodes) {
    const id = ids.get(node.id);
    if (!id) continue;
    const label = escapeMermaidLabel(node.label || node.type);
    lines.push(`  ${id}[${label}]`);
  }

  for (const edge of edges) {
    const from = ids.get(edge.from);
    const to = ids.get(edge.to);
    if (!from || !to) continue;
    if (edge.label) {
      lines.push(`  ${from} -->|${escapeMermaidLabel(edge.label)}| ${to}`);
    } else {
      lines.push(`  ${from} --> ${to}`);
    }
  }

  return lines.join("\n");
}

export function diagramToPlantUml(diagram: ExcalidrawData): string {
  const { nodes, edges } = extractGraph(diagram);
  const ids = new Map(nodes.map((node, idx) => [node.id, `N${idx + 1}`]));

  const lines = ["@startuml"];

  for (const node of nodes) {
    const id = ids.get(node.id);
    if (!id) continue;
    lines.push(`rectangle "${escapePlantUmlLabel(node.label || node.type)}" as ${id}`);
  }

  for (const edge of edges) {
    const from = ids.get(edge.from);
    const to = ids.get(edge.to);
    if (!from || !to) continue;
    if (edge.label) {
      lines.push(`${from} --> ${to} : ${escapePlantUmlLabel(edge.label)}`);
    } else {
      lines.push(`${from} --> ${to}`);
    }
  }

  lines.push("@enduml");
  return lines.join("\n");
}

