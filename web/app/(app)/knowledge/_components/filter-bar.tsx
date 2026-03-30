"use client";

import { useCallback, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Search, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// --------------- Types ---------------

export interface ZettelFilters {
  q?: string;
  topic?: string;
  tags?: string[];
  sort_by?: string;
  sort_dir?: string;
  importance_min?: number;
  status?: string;
}

export interface FilterBarProps {
  filters: ZettelFilters;
  onFiltersChange: (filters: ZettelFilters) => void;
  availableTopics: string[];
  availableTags: string[];
}

// --------------- Constants ---------------

const SORT_OPTIONS = [
  { value: "updated_at:desc", label: "Recently Updated" },
  { value: "created_at:desc", label: "Recently Created" },
  { value: "title:asc", label: "Title A-Z" },
  { value: "importance:desc", label: "Most Important" },
  { value: "confidence:desc", label: "Most Confident" },
];

const IMPORTANCE_OPTIONS = [
  { value: "0", label: "Any" },
  { value: "5", label: "5+" },
  { value: "7", label: "7+" },
];

// --------------- Helpers ---------------

function hasActiveFilters(filters: ZettelFilters): boolean {
  return !!(
    filters.q ||
    filters.topic ||
    (filters.tags && filters.tags.length > 0) ||
    filters.sort_by ||
    (filters.importance_min && filters.importance_min > 0)
  );
}

function currentSortValue(filters: ZettelFilters): string {
  if (!filters.sort_by) return "";
  return `${filters.sort_by}:${filters.sort_dir || "desc"}`;
}

// --------------- Component ---------------

export function FilterBar({
  filters,
  onFiltersChange,
  availableTopics,
  availableTags,
}: FilterBarProps) {
  const update = useCallback(
    (patch: Partial<ZettelFilters>) => {
      onFiltersChange({ ...filters, ...patch });
    },
    [filters, onFiltersChange],
  );

  const clearAll = useCallback(() => {
    onFiltersChange({});
  }, [onFiltersChange]);

  const toggleTag = useCallback(
    (tag: string) => {
      const current = filters.tags || [];
      const next = current.includes(tag)
        ? current.filter((t) => t !== tag)
        : [...current, tag];
      update({ tags: next.length > 0 ? next : undefined });
    },
    [filters.tags, update],
  );

  const handleSortChange = useCallback(
    (value: string) => {
      if (!value) {
        update({ sort_by: undefined, sort_dir: undefined });
        return;
      }
      const [sort_by, sort_dir] = value.split(":");
      update({ sort_by, sort_dir });
    },
    [update],
  );

  const handleImportanceChange = useCallback(
    (value: string) => {
      const num = Number(value);
      update({ importance_min: num > 0 ? num : undefined });
    },
    [update],
  );

  const active = useMemo(() => hasActiveFilters(filters), [filters]);
  const selectedTags = filters.tags || [];
  const [expanded, setExpanded] = useState(false);

  const isOpen = expanded || active;

  const activeCount = [
    filters.q,
    filters.topic,
    filters.tags?.length,
    filters.importance_min && filters.importance_min > 0,
  ].filter(Boolean).length;

  return (
    <div className="border-b border-[var(--alfred-ruled-line)]">
      {/* Collapse toggle */}
      <button
        onClick={() => setExpanded(!isOpen)}
        className="flex w-full items-center gap-2 px-4 py-1.5 text-[11px] uppercase tracking-wider text-[var(--alfred-text-tertiary)] transition-colors hover:text-foreground"
      >
        {isOpen ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        <span className="font-medium">Filters</span>
        {activeCount > 0 && (
          <span className="rounded-full bg-primary px-1.5 py-0.5 text-[9px] font-semibold leading-none text-primary-foreground">
            {activeCount}
          </span>
        )}
        {!isOpen && selectedTags.length > 0 && (
          <span className="ml-1 text-[10px] normal-case tracking-normal text-muted-foreground">
            {selectedTags.join(", ")}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="flex flex-wrap items-center gap-2 px-4 pb-2">
          {/* Search */}
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-[var(--alfred-text-tertiary)]" />
            <Input
              value={filters.q || ""}
              onChange={(e) => update({ q: e.target.value || undefined })}
              placeholder="Search zettels..."
              className="h-8 w-52 pl-8 text-xs"
            />
          </div>

          <div className="mx-1 h-5 w-px bg-[var(--border)]" />

          {/* Topic */}
          {availableTopics.length > 0 && (
            <div className="flex flex-col gap-0.5">
              <span className="text-[10px] font-medium uppercase tracking-[0.1em] text-[var(--alfred-text-tertiary)]">
                Topic
              </span>
              <Select
                value={filters.topic || ""}
                onValueChange={(v) => update({ topic: v === "__all__" ? undefined : v })}
              >
                <SelectTrigger className="h-7 w-36 text-xs">
                  <SelectValue placeholder="All topics" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All topics</SelectItem>
                  {availableTopics.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Sort */}
          <div className="flex flex-col gap-0.5">
            <span className="text-[10px] font-medium uppercase tracking-[0.1em] text-[var(--alfred-text-tertiary)]">
              Sort
            </span>
            <Select
              value={currentSortValue(filters) || ""}
              onValueChange={handleSortChange}
            >
              <SelectTrigger className="h-7 w-40 text-xs">
                <SelectValue placeholder="Default" />
              </SelectTrigger>
              <SelectContent>
                {SORT_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Importance */}
          <div className="flex flex-col gap-0.5">
            <span className="text-[10px] font-medium uppercase tracking-[0.1em] text-[var(--alfred-text-tertiary)]">
              Importance
            </span>
            <div className="flex gap-1">
              {IMPORTANCE_OPTIONS.map((o) => {
                const isActive =
                  (o.value === "0" && !filters.importance_min) ||
                  String(filters.importance_min) === o.value;
                return (
                  <button
                    key={o.value}
                    onClick={() => handleImportanceChange(o.value)}
                    className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : "bg-[var(--alfred-accent-subtle)] text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {o.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Separator */}
          {availableTags.length > 0 && (
            <div className="mx-1 h-5 w-px bg-[var(--border)]" />
          )}

          {/* Tags */}
          {availableTags.length > 0 && (
            <div className="flex flex-col gap-0.5">
              <span className="text-[10px] font-medium uppercase tracking-[0.1em] text-[var(--alfred-text-tertiary)]">
                Tags
              </span>
              <div className="flex max-w-md flex-wrap gap-1">
                {availableTags.slice(0, 12).map((tag) => {
                  const isSelected = selectedTags.includes(tag);
                  return (
                    <Badge
                      key={tag}
                      variant={isSelected ? "default" : "outline"}
                      className={`cursor-pointer text-[10px] transition-colors ${
                        isSelected
                          ? "border-primary bg-primary text-primary-foreground hover:bg-primary/90"
                          : "hover:border-primary/40 hover:text-foreground"
                      }`}
                      onClick={() => toggleTag(tag)}
                    >
                      {tag}
                    </Badge>
                  );
                })}
              </div>
            </div>
          )}

          {/* Clear all */}
          {active && (
            <>
              <div className="flex-1" />
              <Button
                variant="ghost"
                size="sm"
                className="h-7 gap-1 text-[11px] text-primary hover:text-primary/80"
                onClick={clearAll}
              >
                <X className="size-3" />
                Clear filters
              </Button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
