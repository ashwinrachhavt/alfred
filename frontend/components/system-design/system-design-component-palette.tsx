"use client";

import { useMemo, useRef, useState } from "react";
import { GripVertical, Search } from "lucide-react";

import type { ComponentDefinition } from "@/lib/api/types/system-design";
import { useSystemDesignComponents } from "@/features/system-design/queries";
import {
  SYSTEM_DESIGN_COMPONENT_DND_MIME,
  encodeSystemDesignComponentDragPayload,
  toSystemDesignComponentDragPayload,
} from "@/components/system-design/system-design-dnd";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

export type SystemDesignComponentPaletteProps = {
  onInsertComponent: (component: Pick<ComponentDefinition, "id" | "name" | "category">) => void;
};

const CATEGORY_LABELS: Record<string, string> = {
  client: "Client",
  load_balancer: "Load balancer",
  api_gateway: "API gateway",
  microservice: "Services",
  database: "Databases",
  cache: "Caches",
  message_queue: "Queues",
  cdn: "CDN",
  storage: "Storage",
  other: "Other",
};

function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category.replaceAll("_", " ");
}

const EMPTY_COMPONENTS: ComponentDefinition[] = [];

type GroupedComponents = Array<{ category: string; label: string; items: ComponentDefinition[] }>;

function groupComponents(components: ComponentDefinition[]): GroupedComponents {
  const groups = new Map<string, ComponentDefinition[]>();
  for (const component of components) {
    const key = component.category;
    const existing = groups.get(key);
    if (existing) {
      existing.push(component);
    } else {
      groups.set(key, [component]);
    }
  }

  return [...groups.entries()]
    .map(([category, items]) => ({
      category,
      label: categoryLabel(category),
      items: items.slice().sort((a, b) => a.name.localeCompare(b.name)),
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

export function SystemDesignComponentPalette({ onInsertComponent }: SystemDesignComponentPaletteProps) {
  const componentsQuery = useSystemDesignComponents();
  const [query, setQuery] = useState("");
  const draggingIdRef = useRef<string | null>(null);

  const components = useMemo(
    () => componentsQuery.data ?? EMPTY_COMPONENTS,
    [componentsQuery.data],
  );
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return components;

    return components.filter((component) => {
      const haystack = `${component.name} ${component.description}`.toLowerCase();
      return haystack.includes(needle);
    });
  }, [components, query]);

  const grouped = useMemo(() => groupComponents(filtered), [filtered]);

  return (
    <aside className="bg-muted/20 flex w-60 flex-col border-r">
      <div className="space-y-2 p-3">
        <div className="text-xs font-semibold tracking-wide uppercase">Components</div>
        <div className="relative">
          <Search className="text-muted-foreground absolute top-2.5 left-2 size-4" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search…"
            className="h-9 pl-8"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {componentsQuery.isPending ? (
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : componentsQuery.error ? (
          <p className="text-muted-foreground text-sm">
            Unable to load component library.{" "}
            <span className="text-muted-foreground/70">
              {(componentsQuery.error as Error).message}
            </span>
          </p>
        ) : grouped.length === 0 ? (
          <p className="text-muted-foreground text-sm">No matching components.</p>
        ) : (
          <div className="space-y-4">
            {grouped.map((group) => (
              <section key={group.category} className="space-y-2">
                <div className="text-muted-foreground flex items-center justify-between text-xs font-medium">
                  <span className="uppercase tracking-wide">{group.label}</span>
                  <Badge variant="secondary" className="text-[10px]">
                    {group.items.length}
                  </Badge>
                </div>

                <div className="space-y-2">
                  {group.items.map((component) => (
                    <button
                      key={component.id}
                      type="button"
                      draggable
                      className="bg-background hover:bg-accent focus-visible:ring-ring/50 w-full rounded-lg border px-3 py-2 text-left shadow-xs transition-colors outline-none focus-visible:ring-[3px]"
                      onClick={() => {
                        if (draggingIdRef.current === component.id) return;
                        onInsertComponent(component);
                      }}
                      onDragStart={(event) => {
                        draggingIdRef.current = component.id;
                        const payload = toSystemDesignComponentDragPayload(component);
                        event.dataTransfer.effectAllowed = "copy";
                        event.dataTransfer.setData(
                          SYSTEM_DESIGN_COMPONENT_DND_MIME,
                          encodeSystemDesignComponentDragPayload(payload),
                        );
                        event.dataTransfer.setData("text/plain", component.name);
                      }}
                      onDragEnd={() => {
                        window.setTimeout(() => {
                          if (draggingIdRef.current === component.id) draggingIdRef.current = null;
                        }, 0);
                      }}
                      title="Click to insert, or drag onto the canvas"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium">{component.name}</div>
                          <div className="text-muted-foreground mt-0.5 line-clamp-2 text-xs leading-snug">
                            {component.description}
                          </div>
                        </div>
                        <div className="text-muted-foreground mt-0.5 flex items-center gap-1">
                          <GripVertical className="size-4" />
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>

      <div className="text-muted-foreground border-t px-3 py-2 text-xs">
        Tip: Drag a component onto the canvas.
      </div>
    </aside>
  );
}
