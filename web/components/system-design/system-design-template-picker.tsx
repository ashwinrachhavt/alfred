"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { TemplateDefinition } from "@/lib/api/types/system-design";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const THUMBNAIL_CACHE = new Map<string, string>();

function readTemplateMermaid(template: TemplateDefinition): string | null {
 const metadata = template.diagram.metadata;
 if (!metadata || typeof metadata !== "object") return null;
 const mermaid = (metadata as Record<string, unknown>).mermaid;
 return typeof mermaid === "string" && mermaid.trim() ? mermaid.trim() : null;
}

async function buildThumbnailSvg(template: TemplateDefinition): Promise<string | null> {
 const cached = THUMBNAIL_CACHE.get(template.id);
 if (cached) return cached;

 const [{ exportToSvg, convertToExcalidrawElements }, { parseMermaidToExcalidraw }] =
 await Promise.all([import("@excalidraw/excalidraw"), import("@excalidraw/mermaid-to-excalidraw")]);

 const mermaid = readTemplateMermaid(template);

 let elements: unknown = template.diagram.elements;
 let appState: unknown = template.diagram.appState;
 let files: unknown = template.diagram.files;

 if (mermaid) {
 const parsed = await parseMermaidToExcalidraw(mermaid);
 elements = convertToExcalidrawElements(parsed.elements, { regenerateIds: true });
 appState = {};
 files = {};
 }

 const svgEl = await Promise.resolve(
 exportToSvg({
 elements: elements as never,
 appState: appState as never,
 files: files as never,
 exportPadding: 10,
 }),
 );

 svgEl.setAttribute("width", "100%");
 svgEl.setAttribute("height", "100%");
 svgEl.setAttribute("preserveAspectRatio", "xMidYMid meet");

 const markup = svgEl.outerHTML;
 THUMBNAIL_CACHE.set(template.id, markup);
 return markup;
}

function SystemDesignTemplateThumbnail({ template }: { template: TemplateDefinition }) {
 const [markup, setMarkup] = useState<string | null>(THUMBNAIL_CACHE.get(template.id) ?? null);
 const cancelledRef = useRef(false);

 useEffect(() => {
 cancelledRef.current = false;

 void buildThumbnailSvg(template)
 .then((svg) => {
 if (!cancelledRef.current) setMarkup(svg);
 })
 .catch(() => {
 if (!cancelledRef.current) setMarkup(null);
 });

 return () => {
 cancelledRef.current = true;
 };
 }, [template]);

 return (
 <div className="bg-muted/40 relative aspect-[16/9] w-full overflow-hidden rounded-md border">
 {markup ? (
 <div
 className="pointer-events-none absolute inset-0 [&>svg]:h-full [&>svg]:w-full"
 // Excalidraw export is generated locally; safe to render.
 dangerouslySetInnerHTML={{ __html: markup }}
 />
 ) : (
 <div className="text-muted-foreground flex h-full w-full items-center justify-center text-xs">
 Preview unavailable
 </div>
 )}
 </div>
 );
}

export function SystemDesignTemplatePicker({
 templates,
 selectedTemplateId,
 onSelectTemplateId,
}: {
 templates: TemplateDefinition[];
 selectedTemplateId: string | null;
 onSelectTemplateId: (next: string | null) => void;
}) {
 const [query, setQuery] = useState("");

 const filtered = useMemo(() => {
 const q = query.trim().toLowerCase();
 if (!q) return templates;
 return templates.filter((t) => {
 return (
 t.name.toLowerCase().includes(q) ||
 t.description.toLowerCase().includes(q) ||
 t.components.some((c) => c.toLowerCase().includes(q))
 );
 });
 }, [query, templates]);

 return (
 <div className="space-y-3">
 <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
 <div className="space-y-1">
 <p className="text-sm font-medium">Templates</p>
 <p className="text-muted-foreground text-xs">
 Pick a starting point, then fully edit it on the canvas.
 </p>
 </div>
 <Input
 value={query}
 onChange={(e) => setQuery(e.target.value)}
 placeholder="Search templates…"
 className="sm:w-64"
 />
 </div>

 <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
 <Card
 role="button"
 tabIndex={0}
 className={cn(
 "hover:bg-accent/30 cursor-pointer overflow-hidden transition-colors",
 !selectedTemplateId ? "ring-primary ring-2" : "",
 )}
 onClick={() => onSelectTemplateId(null)}
 onKeyDown={(e) => {
 if (e.key === "Enter" || e.key === " ") onSelectTemplateId(null);
 }}
 >
 <div className="p-4">
 <div className="bg-muted/40 flex aspect-[16/9] items-center justify-center rounded-md border">
 <span className="text-muted-foreground text-xs">No template</span>
 </div>
 <div className="space-y-1 pt-3">
 <p className="text-sm font-semibold">Start from scratch</p>
 <p className="text-muted-foreground text-xs">Blank board and notes.</p>
 </div>
 </div>
 </Card>

 {filtered.map((template) => {
 const isSelected = template.id === selectedTemplateId;
 return (
 <Card
 key={template.id}
 role="button"
 tabIndex={0}
 className={cn(
 "hover:bg-accent/30 cursor-pointer overflow-hidden transition-colors",
 isSelected ? "ring-primary ring-2" : "",
 )}
 onClick={() => onSelectTemplateId(template.id)}
 onKeyDown={(e) => {
 if (e.key === "Enter" || e.key === " ") onSelectTemplateId(template.id);
 }}
 >
 <div className="p-4">
 <SystemDesignTemplateThumbnail template={template} />
 <div className="space-y-1 pt-3">
 <p className="text-sm font-semibold">{template.name}</p>
 <p className="text-muted-foreground line-clamp-2 text-xs">{template.description}</p>
 </div>
 {template.components.length ? (
 <div className="flex flex-wrap gap-1 pt-3">
 {template.components.slice(0, 6).map((c) => (
 <Badge key={c} variant="secondary" className="text-[10px]">
 {c}
 </Badge>
 ))}
 {template.components.length > 6 ? (
 <Badge variant="outline" className="text-[10px]">
 +{template.components.length - 6}
 </Badge>
 ) : null}
 </div>
 ) : null}
 </div>
 </Card>
 );
 })}
 </div>
 </div>
 );
}
