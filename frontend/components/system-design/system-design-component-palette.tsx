"use client";

import { useMemo, useState } from "react";
import { Search, Star } from "lucide-react";

import { useSystemDesignComponents } from "@/features/system-design/queries";
import type { ComponentDefinition } from "@/lib/api/types/system-design";

import { cn } from "@/lib/utils";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type StoredIds = string[];

const FAVORITES_KEY = "alfred:system-design:component-favorites:v1";
const RECENTS_KEY = "alfred:system-design:component-recents:v1";
const RECENTS_LIMIT = 12;

function readStoredIds(key: string): StoredIds {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as string[]) : [];
  } catch {
    return [];
  }
}

function writeStoredIds(key: string, value: StoredIds): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage failures (private mode, quota, etc.)
  }
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
  const haystack = `${component.name} ${component.description} ${component.category}`.toLowerCase();
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

  function handleInsert(component: ComponentDefinition) {
    onInsert({ id: component.id, name: component.name, category: component.category });
    registerRecent(component.id);
  }

  const favoriteComponents = useMemo(() => {
    if (!favorites.size) return [];
    return Array.from(favorites)
      .map((id) => byId.get(id))
      .filter(Boolean) as ComponentDefinition[];
  }, [byId, favorites]);

  const recentComponents = useMemo(() => {
    if (!recents.length) return [];
    return recents.map((id) => byId.get(id)).filter(Boolean) as ComponentDefinition[];
  }, [byId, recents]);

  const errorMessage = error instanceof Error ? error.message : error ? "Failed to load components." : null;

  return (
    <div className={cn("flex min-h-0 flex-1 flex-col gap-4 p-4", className)}>
      {showHeader ? (
        <div className="space-y-1">
          <h2 className="text-base font-semibold">Components</h2>
          <p className="text-muted-foreground text-xs">
            Search and click to drop a component onto the canvas.
          </p>
        </div>
      ) : null}

      <div className="relative">
        <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search components…"
          className="pl-9"
          disabled={isPending}
        />
      </div>

      {errorMessage ? <p className="text-destructive text-sm">{errorMessage}</p> : null}

      {isPending ? (
        <p className="text-muted-foreground text-sm">Loading component library…</p>
      ) : null}

      {!isPending && !components.length ? (
        <p className="text-muted-foreground text-sm">No components available.</p>
      ) : null}

      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto pr-1">
        {favoriteComponents.length ? (
          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium">Favorites</h3>
              <Badge variant="secondary">{favoriteComponents.length}</Badge>
            </div>
            <div className="space-y-2">
              {favoriteComponents.map((component) => (
                <ComponentRow
                  key={component.id}
                  component={component}
                  isFavorite
                  onToggleFavorite={toggleFavorite}
                  onInsert={handleInsert}
                />
              ))}
            </div>
          </section>
        ) : null}

        {recentComponents.length ? (
          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium">Recent</h3>
              <Badge variant="secondary">{recentComponents.length}</Badge>
            </div>
            <div className="space-y-2">
              {recentComponents.map((component) => (
                <ComponentRow
                  key={component.id}
                  component={component}
                  isFavorite={favorites.has(component.id)}
                  onToggleFavorite={toggleFavorite}
                  onInsert={handleInsert}
                />
              ))}
            </div>
          </section>
        ) : null}

        {groups.map(([category, items]) => (
          <section key={category} className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium">{formatCategory(category)}</h3>
              <Badge variant="outline">{items.length}</Badge>
            </div>
            <div className="space-y-2">
              {items.map((component) => (
                <ComponentRow
                  key={component.id}
                  component={component}
                  isFavorite={favorites.has(component.id)}
                  onToggleFavorite={toggleFavorite}
                  onInsert={handleInsert}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function ComponentRow({
  component,
  isFavorite,
  onToggleFavorite,
  onInsert,
}: {
  component: ComponentDefinition;
  isFavorite: boolean;
  onToggleFavorite: (id: string) => void;
  onInsert: (component: ComponentDefinition) => void;
}) {
  return (
    <div className="bg-background flex items-start justify-between gap-3 rounded-lg border p-3">
      <button
        type="button"
        onClick={() => onInsert(component)}
        className="min-w-0 flex-1 space-y-1 text-left"
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
