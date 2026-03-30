"use client";

import { useMemo, useState } from "react";
import { GripVertical, Search, Star } from "lucide-react";

import { safeGetJSON, safeSetJSON } from "@/lib/storage";
import type { ComponentDefinition } from "@/lib/api/types/system-design";
import { useSystemDesignComponents } from "@/features/system-design/queries";
import { cn } from "@/lib/utils";

import {
 SYSTEM_DESIGN_COMPONENT_DND_MIME,
 encodeSystemDesignComponentDragPayload,
 toSystemDesignComponentDragPayload,
} from "@/components/system-design/system-design-dnd";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type StoredIds = string[];

const FAVORITES_KEY = "alfred:system-design:component-favorites:v1";
const RECENTS_KEY = "alfred:system-design:component-recents:v1";
const RECENTS_LIMIT = 12;

function readStoredIds(key: string): StoredIds {
 if (typeof window === "undefined") return [];
 const parsed = safeGetJSON<unknown>(key);
 return Array.isArray(parsed) ? (parsed as string[]) : [];
}

function writeStoredIds(key: string, value: StoredIds): void {
 if (typeof window === "undefined") return;
 safeSetJSON(key, value);
}

function formatCategory(category: string): string {
 return category
 .split("_")
 .filter(Boolean)
 .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
 .join(" ");
}

function scoreForQuery(component: ComponentDefinition, query: string): number {
 if (!query) return 0;
 const haystack =`${component.name} ${component.description} ${component.category}`.toLowerCase();
 const needle = query.toLowerCase();
 if (component.name.toLowerCase().includes(needle)) return 3;
 if (component.category.toLowerCase().includes(needle)) return 2;
 if (haystack.includes(needle)) return 1;
 return 0;
}

export type SystemDesignComponentPaletteProps = {
 onInsert: (component: Pick<ComponentDefinition, "id" | "name" | "category">) => void;
 className?: string;
 showHeader?: boolean;
};

function ComponentRow({
 component,
 isFavorite,
 onInsert,
 onToggleFavorite,
}: {
 component: ComponentDefinition;
 isFavorite: boolean;
 onInsert: (component: Pick<ComponentDefinition, "id" | "name" | "category">) => void;
 onToggleFavorite: (id: string) => void;
}) {
 return (
 <div className="bg-background flex items-start justify-between gap-3 rounded-lg border p-3">
 <button
 type="button"
 draggable
 onClick={() => onInsert(component)}
 onDragStart={(event) => {
 event.dataTransfer.effectAllowed = "copy";
 const payload = toSystemDesignComponentDragPayload(component);
 event.dataTransfer.setData(
 SYSTEM_DESIGN_COMPONENT_DND_MIME,
 encodeSystemDesignComponentDragPayload(payload),
 );
 event.dataTransfer.setData("text/plain", component.name);
 }}
 className="min-w-0 flex-1 space-y-1 text-left"
 title="Click to insert, or drag onto the canvas"
 >
 <div className="flex flex-wrap items-center gap-2">
 <span className="truncate text-sm font-medium">{component.name}</span>
 <Badge variant="secondary" className="whitespace-nowrap">
 {formatCategory(component.category)}
 </Badge>
 </div>
 <p className="text-muted-foreground line-clamp-2 text-xs">{component.description}</p>
 </button>

 <div className="flex items-center gap-1">
 <span className="text-muted-foreground">
 <GripVertical className="size-4" />
 </span>
 <Button
 type="button"
 variant="ghost"
 size="icon-sm"
 className="text-muted-foreground hover:text-foreground"
 onClick={() => onToggleFavorite(component.id)}
 title={isFavorite ? "Remove favorite" : "Add favorite"}
 >
 <Star className="size-4" fill={isFavorite ? "currentColor" : "none"} />
 </Button>
 </div>
 </div>
 );
}

export function SystemDesignComponentPalette({
 onInsert,
 className,
 showHeader = true,
}: SystemDesignComponentPaletteProps) {
 const { data: components = [], isPending, error } = useSystemDesignComponents();

 const [query, setQuery] = useState("");
 const [favorites, setFavorites] = useState<Set<string>>(
 () => new Set(readStoredIds(FAVORITES_KEY)),
 );
 const [recents, setRecents] = useState<string[]>(() => readStoredIds(RECENTS_KEY));

 const byId = useMemo(() => {
 return new Map(components.map((c) => [c.id, c]));
 }, [components]);

 const filtered = useMemo(() => {
 const trimmed = query.trim();
 if (!trimmed) return components;
 return components
 .map((component) => ({ component, score: scoreForQuery(component, trimmed) }))
 .filter((entry) => entry.score > 0)
 .sort((a, b) => b.score - a.score || a.component.name.localeCompare(b.component.name))
 .map((entry) => entry.component);
 }, [components, query]);

 const groups = useMemo(() => {
 const grouped = new Map<string, ComponentDefinition[]>();
 for (const component of filtered) {
 const key = component.category || "other";
 const existing = grouped.get(key) ?? [];
 existing.push(component);
 grouped.set(key, existing);
 }
 return Array.from(grouped.entries()).sort((a, b) => a[0].localeCompare(b[0]));
 }, [filtered]);

 function toggleFavorite(id: string) {
 setFavorites((prev) => {
 const next = new Set(prev);
 if (next.has(id)) next.delete(id);
 else next.add(id);
 writeStoredIds(FAVORITES_KEY, Array.from(next));
 return next;
 });
 }

 function registerRecent(id: string) {
 setRecents((prev) => {
 const next = [id, ...prev.filter((existing) => existing !== id)].slice(0, RECENTS_LIMIT);
 writeStoredIds(RECENTS_KEY, next);
 return next;
 });
 }

 function insert(component: Pick<ComponentDefinition, "id" | "name" | "category">) {
 registerRecent(component.id);
 onInsert(component);
 }

 const favoriteComponents = useMemo(() => {
 const items: ComponentDefinition[] = [];
 for (const id of favorites) {
 const component = byId.get(id);
 if (component) items.push(component);
 }
 return items.sort((a, b) => a.name.localeCompare(b.name));
 }, [byId, favorites]);

 const recentComponents = useMemo(() => {
 const items: ComponentDefinition[] = [];
 for (const id of recents) {
 const component = byId.get(id);
 if (component) items.push(component);
 }
 return items;
 }, [byId, recents]);

 return (
 <div className={cn("flex h-full flex-col gap-3", className)}>
 {showHeader ? (
 <div className="space-y-1">
 <div className="text-sm font-medium">Component library</div>
 <div className="text-muted-foreground text-xs">Click to insert, or drag onto canvas.</div>
 </div>
 ) : null}

 <div className="relative">
 <Search className="text-muted-foreground absolute top-2.5 left-2.5 size-4" />
 <Input
 value={query}
 onChange={(event) => setQuery(event.target.value)}
 placeholder="Search components…"
 className="pl-9"
 />
 </div>

 {isPending ? (
 <div className="text-muted-foreground text-sm">Loading components…</div>
 ) : error ? (
 <div className="text-destructive text-sm">Failed to load components.</div>
 ) : (
 <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
 {favoriteComponents.length ? (
 <div className="space-y-2">
 <div className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
 Favorites
 </div>
 <div className="space-y-2">
 {favoriteComponents.map((component) => (
 <ComponentRow
 key={component.id}
 component={component}
 isFavorite={favorites.has(component.id)}
 onInsert={insert}
 onToggleFavorite={toggleFavorite}
 />
 ))}
 </div>
 </div>
 ) : null}

 {recentComponents.length ? (
 <div className="space-y-2">
 <div className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
 Recent
 </div>
 <div className="space-y-2">
 {recentComponents.map((component) => (
 <ComponentRow
 key={component.id}
 component={component}
 isFavorite={favorites.has(component.id)}
 onInsert={insert}
 onToggleFavorite={toggleFavorite}
 />
 ))}
 </div>
 </div>
 ) : null}

 <div className="space-y-4">
 {groups.map(([category, items]) => (
 <div key={category} className="space-y-2">
 <div className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
 {formatCategory(category)}
 </div>
 <div className="space-y-2">
 {items.map((component) => (
 <ComponentRow
 key={component.id}
 component={component}
 isFavorite={favorites.has(component.id)}
 onInsert={insert}
 onToggleFavorite={toggleFavorite}
 />
 ))}
 </div>
 </div>
 ))}
 </div>
 </div>
 )}
 </div>
 );
}
